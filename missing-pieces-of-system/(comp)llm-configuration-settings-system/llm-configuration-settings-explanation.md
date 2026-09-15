# A single, switchable LLM configuration + reliability layer

## Context

This came out of a conversation about making every agent's LLM usage
configurable in one place — which model/endpoint a given step uses, so
it can be switched (local vs. frontier) without touching code — which
led into a read-only audit of how LLM calls actually work today across
`vinu-agent` and `vinu-research`. The audit found real, specific gaps in
four areas: model/tier selection, retry logic, response parsing, and
whether an LLM failure ever becomes visible to a human. This doc covers
all four together because they're one coherent piece of work — the same
shared wrapper that fixes retry/parsing is also the natural place to plug
in role-based config and failure alerting.

**Decided already, not open questions**: the shared client speaks
OpenAI-compatible wire format only, for now — covers OpenAI itself,
Ollama, vLLM, LM Studio, OpenRouter, Groq, Together, and most other
serious backends. `vinu-agent`'s native-Anthropic-SDK path
(`AnthropicChatLLM`) is explicitly deferred, not designed for here — "we
will see in the future," Anthropic or any other non-OpenAI-compatible
provider is out of scope until actually needed. `tenacity` is the chosen
retry library (reasoning below).

## What already exists (the raw material, and its real gaps)

**Model/tier selection — partial, only one hardcoded split.**
`vinu-agent/vinu_agent/config.py:158-183` builds a distinct
`orchestrator_llm` from `VINU_ORCHESTRATOR_LLM_*` env vars, separate from
the shared `AgentConfig.llm` every team/specialist uses
(`agent/team.py`, built once in `service.py` via `create_llm(config.llm)`
and passed down to every manager/specialist — the `tier=` argument seen
in `wrap_with_logging` calls, `agent/llm.py`, is a **logging label only**,
it does not select a model). `vinu-infra/llm/config.py`'s `LlmConfig.from_env`
and `vinu-research/vinu_research/config.py` each read one flat
model/base_url from env — no per-role override mechanism beyond the one
orchestrator special case. Defaults across all three packages point at
local Ollama (`http://127.0.0.1:11434/v1`, `llama3.2`); the orchestrator
is the only role that defaults to a frontier model (`gpt-4o-mini`).

**Retry logic — exists, duplicated three times, drifting.**
- `vinu-infra/llm/client.py` (sync) and `client_async.py` (async) each
  implement their own near-identical retry loop: exponential backoff
  `(2**attempt)*1.0`, `retry_max` from config (default 3), retries on
  connection errors and transient HTTP (429/5xx), honors `Retry-After`
  with jitter on 429, also tries `alternative_urls()` for Docker
  networking.
- `vinu-agent/vinu_agent/agent/llm.py` implements a **third, separate**
  retry implementation per provider class (`OpenAIChatLLM`,
  `AnthropicChatLLM`, `OllamaChatLLM`) — each with its own copy of
  similar backoff/jitter/Retry-After logic, but not identical (e.g.
  `OllamaChatLLM` doesn't honor Retry-After/jitter on 429 the way the
  others do). Critically, **vinu-agent bypasses the shared vinu-infra
  client entirely** — it talks to the OpenAI/Anthropic SDKs and raw
  `requests.post` to Ollama directly, so it never gets whatever the
  shared client's retry policy is.

**Response parsing — two disconnected conventions, no retry-on-parse-failure anywhere.**
- `vinu-infra/llm/client.py`/`client_async.py`: a shared
  `_parse_json_content()` helper (strips markdown code fences,
  `json.loads`), used only by `chat_json()`. On `KeyError`/
  `JSONDecodeError` it logs, records telemetry, and returns `None` —
  it does **not** retry on a parse failure, only on connection/HTTP
  errors.
- `vinu-agent/vinu_agent/agent/llm.py`'s `ChatLLM.chat()` returns a raw
  `content: str` with **no JSON extraction or validation at all** —
  parsing, if any, is left entirely to whichever caller is up the stack.
- No shared parsing/validation utility spans both packages.

**Logging — exists, entirely write-only.**
Three separate sinks (`llm_calls.jsonl` in vinu-infra, the `llm_calls`
SQLite table in vinu-agent's `LlmCallLogStore`, `telemetry.db`'s
`llm_calls`/`steps` tables) all get written to on every call, but per the
full storage audit (`project-understanding/05-full-recorded-information/`),
**none of them have a production reader** — nothing queries any of them
back. "Logging" today means "recorded somewhere nobody looks."

**Failure alerting — does not exist for LLM health specifically, and one real correctness risk.**
Traced what actually happens when a call fails after retries or returns
garbage:
- `vinu-research/vinu_research/forecast_skill.py:202-212` — when
  `chat_json()` returns `None`/non-dict, it's caught and silently
  replaced with a **fake neutral forecast**
  (`direction="neutral", confidence=0.0`), logged only via
  `logger.warning`. The trade-plan pipeline then continues as if that
  were a genuine low-signal read from the model — **an LLM failure is
  indistinguishable from a real "the model looked and saw nothing"
  result**, which means a real trade-plan decision could be shaped by a
  forecast that never actually happened.
- `vinu-agent/vinu_agent/agent/team.py:388-427` — a failed team run just
  writes `team_runs.status=FAILED` + `error_message`; no retry
  escalation, no notification.
- `vinu-agent/vinu_agent/agent/scheduler_workers.py:426-451` — per-ticker
  worker failures are caught individually, logged via `LOG.exception`,
  and folded into a batch results dict; the cycle itself never surfaces
  this anywhere a human would see it.
- `vinu-agent/vinu_agent/agent/significance_triage.py` — the **one**
  mechanism in the system that pushes anything to a human via
  Telegram/Discord — has exactly three detectors (repeated
  `risk_gatekeeper` rejection, large funding, thesis contradiction), all
  reading `TickerLedgerStore` trading-decision events. **None of them
  inspect LLM call success/failure, retry counts, or `telemetry.db`.**
  There is no `detect_llm_failure_pattern` or equivalent.
- One genuine zero-trace swallow (not the LLM call itself, but adjacent):
  `agent/loop.py:623-624`, a bare `except Exception: pass` around a
  post-hoc `FactAuditor` step.

**The one thing that's already working well and should be preserved.**
`vinu-infra/llm/cache.py`'s `LlmCache` (table `llm_cache`) is genuinely
**actively read on every call** — a real cache-hit path, unlike
everything else logged above. Whatever replaces the current clients must
keep this cache-check-before-retry-loop behavior, not regress it.

## The design

### 1. Role-based model configuration — one YAML, one loader

`vinu-infra/llm/roles.yaml`:

```yaml
default:
  provider: openai_compatible
  base_url: http://127.0.0.1:11434/v1
  model: llama3.2
  api_key_env: ""

roles:
  orchestrator:
    base_url: https://api.openai.com/v1
    model: gpt-4o-mini
    api_key_env: OPENAI_API_KEY
  risk_gatekeeper:
    base_url: https://api.openai.com/v1
    model: gpt-4o-mini
    api_key_env: OPENAI_API_KEY
  forecast_skill:
    base_url: https://api.openai.com/v1
    model: gpt-4o
    api_key_env: OPENAI_API_KEY
  summary_agent: {}        # inherits `default` -- local is fine here
  capital_allocator: {}
  planner: {}
```

A role missing from the file inherits `default` — adding a new agent
role never requires editing this file first; it just runs on the default
model until someone deliberately upgrades it. This generalizes the one
existing precedent (`VINU_ORCHESTRATOR_LLM_*` vs. everything else) into
an arbitrary N-way split, instead of replacing it with something
unrelated.

Every field stays env-overridable per role
(`VINU_LLM_ROLE_RISK_GATEKEEPER_MODEL=...`), matching the
dataclass-defaults-plus-env-override convention every `config.py` in this
repo already uses — so a deployment can flip one role's model without
editing the YAML at all.

One loader function, `vinu_infra.llm.roles.get_llm_config_for_role(role: str) -> LlmConfig`:
reads the YAML once (cached), applies env overrides, returns the existing
`LlmConfig` dataclass shape — no new config type, reuses what
`vinu-infra/llm/config.py` already defines.

### 2. The shared wrapper/policy layer

One client, replacing all three existing implementations, living in
`vinu-infra` (the one place every package already imports shared LLM
code from — same reasoning as `SQLiteBackend`, `telemetry.py`,
`calibration_log.py`). It owns:

- **Config resolution** — takes a `role: str`, resolves it via
  `get_llm_config_for_role()`, so callers say "I am the
  `risk_gatekeeper`," never "call this specific base_url/model."
- **Timeout** — one configured value, per-role overridable the same way
  as model/base_url.
- **Connection/health check** — a cheap, cached "is this endpoint
  currently reachable" pre-flight, so a dead local Ollama instance fails
  fast with a clear error instead of hanging through a full retry cycle
  on every call.
- **Cache check** — preserves `LlmCache`'s existing, working
  cache-before-call behavior; not a new mechanism, just kept in the new
  wrapper instead of being reimplemented per client.
- **Retry, via `tenacity`** — replaces all three hand-rolled
  implementations with one policy:
  - `wait_random_exponential` for backoff+jitter (matches the existing
    intent of all three current implementations, but tested/maintained
    upstream instead of hand-rolled).
  - `stop_after_attempt(retry_max)` — same `retry_max` config knob that
    exists today, just applied once instead of three times.
  - A custom `wait` callable to honor a `Retry-After` header on a 429 —
    the one piece of current behavior not free out of the box, ported
    from the existing implementations' logic.
  - `retry_if_exception_type` for connection/HTTP transient failures
    (what exists today) **plus `retry_if_result`/a raised
    `LlmParseError`** for a failed parse — this is the fix for "nothing
    retries on a parse failure" found in the audit. A single malformed
    JSON response gets a real second chance before being treated as a
    genuine failure, the same courtesy a dropped connection already
    gets.
  - `before_sleep`/`after` callback hooks — the wiring point for the
    failure-counter feeding the significance detector below.
- **Unified parsing** — one JSON-extraction path (the existing
  `_parse_json_content()` logic, kept, not reinvented) used by every
  caller in both packages, replacing vinu-agent's raw-string-with-no-parsing
  path.
- **On final failure (retries exhausted): raise, don't fake a neutral answer.**
  A typed exception (e.g. `LlmCallFailed`), not a `None` a caller can
  mistake for "a real answer that happens to be empty." This is what
  directly closes the `forecast_skill.py` gap — a caller either handles
  the exception explicitly and *labels* the result as
  failure-derived (not a genuine neutral read), or lets it propagate,
  but it can no longer disappear into a value indistinguishable from a
  real forecast.

### 3. Failure surfacing — a new significance detector

`agent/significance_triage.py` gets a fourth detector,
`detect_llm_failure_pattern`, alongside the existing three
(repeated-rejection, large-funding, thesis-contradiction). It watches
the failure counter the wrapper's `before_sleep`/`after` hooks feed (a
simple rolling count — doesn't need a new store; the counter can live in
`ticker_ledger`/a small in-memory structure, following the existing
pattern of the other three detectors reading `TickerLedgerStore`) and
fires the same way they do: a Telegram/Discord message via the existing
`deliver_flag` path (`significance_triage.py:328-345`) — no new delivery
mechanism, reuse what's already wired up. This is what actually makes an
LLM outage or a bad model swap **visible in real time**, instead of
sitting in a write-only log table.

### 4. Migration — what moves, in what order

Roughly a dozen call sites across `vinu-agent` and `vinu-research`
currently construct their own LLM client object directly instead of
going through a shared surface:

- `vinu-agent/vinu_agent/service.py` — `create_llm(config.llm)`,
  `orchestrator_llm` construction.
- `vinu-agent/vinu_agent/agent/team.py` — every manager/specialist.
- `vinu-research/vinu_research/llm.py`'s `ResearchLlmClient` — already
  closer to using the shared vinu-infra client; smaller lift.
- `vinu-agent/vinu_agent/agent/llm.py`'s `OpenAIChatLLM`/`AnthropicChatLLM`/
  `OllamaChatLLM` — the three provider classes being replaced (Anthropic
  path deferred/dropped per the decision above, not migrated).

Recommended order: (1) build the YAML + loader + wrapper in `vinu-infra`
as new code, nothing else changes yet; (2) migrate `vinu-research`'s
`ResearchLlmClient` first — smallest gap to the target state, lowest
risk; (3) migrate `vinu-agent`'s `service.py`/`team.py` construction
sites to call the wrapper via role, retiring `agent/llm.py`'s three
provider classes; (4) add the `detect_llm_failure_pattern` significance
detector last, once the wrapper's failure counter actually exists to
watch.

## Scope note

This is a real refactor, not a config tweak — it touches every call site
that currently constructs its own LLM client object (roughly a dozen
across two packages), adds one new dependency (`tenacity`), and changes
what a caller receives on failure (an exception instead of a silent
`None`/fake value) — which means every caller of `chat_json()`/`chat()`
needs to be checked for whether it already handles an exception
correctly or was relying on the old silent-`None` behavior. Like the
narrating-agent and maturity-agentic-system work, this should get its
own sized, standalone implementation pass rather than being folded into
smaller fixes — but unlike those two (which are net-new capability), this
one is fixing a correctness gap (`forecast_skill.py`'s silent fake
neutral forecast) that already affects trade-plan decisions today, so
it's worth prioritizing ahead of net-new agent capability, not just
alongside it.
