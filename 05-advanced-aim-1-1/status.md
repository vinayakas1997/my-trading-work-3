---
name: observability-telemetry-layer-status
status: steps-1-4-implemented
purpose: build log for AGENTS.md's "how to proceed" steps 1-4 (shared schema, wire into vinu-lib, fix vinu-agent's LLM client, SQLite table) plus a first pass at step 5 (tool-call telemetry) — what actually landed, file:line, and what's still open. Companion to AGENTS.md (the design/why); this file is the record of what happened.
---

# Build Log — What Actually Landed

## What was built

**1. Shared schema + SQLite store** —
[`vinu-components/vinu-lib/telemetry.py`](../vinu-components/vinu-lib/telemetry.py):
`LLMCallRecord` (service, model, base_url, prompt/completion/total tokens,
`token_count_source: "provider"|"estimated"`, `retry_count`, `latency_sec`,
`success`, `outcome`, `error`) and `StepRecord` (service, step_name,
duration_sec, success, `outcome` as an explicit reason code, data volume
in/out, error) — both persisted via a new `TelemetryStore(SQLiteBackend)`
with two tables (`llm_calls`, `steps`), following the exact base-class
pattern every other service's store already uses
(`04-vinu-components-integration-plan.md` §2's "one relational pattern,
reused, not reinvented"). `get_telemetry_store(db_path)` caches one store
per resolved path — deliberately not a single implicit-location singleton,
per AGENTS.md's design decision to avoid the class of bug
`data-root-docker-path-mismatch.md` already found elsewhere in this
project. `record_llm_call_safe`/`record_step_safe` wrap writes in
`try/except: pass`, matching this project's established pattern (e.g.
`session/service.py`'s debrief-detector) for never letting an
observability side-effect break the thing it's observing. 10 tests,
[`vinu-lib/tests/test_telemetry.py`](../vinu-components/vinu-lib/tests/test_telemetry.py).

**2. Wired into `vinu-lib`'s existing LLM clients** —
[`vinu-lib/llm/client.py`](../vinu-components/vinu-lib/llm/client.py) and
[`client_async.py`](../vinu-components/vinu-lib/llm/client_async.py): both
already logged tokens/duration to `data/llm_calls.jsonl`
(`_log_llm_call`) but never tracked retry count. Added a `total_attempts`
counter across the existing candidate-URL × retry loop and record an
`LLMCallRecord` on every return path (success, parse error, all-endpoints-
failed) — additive, the existing JSONL log and `CostTracker` recording are
untouched. Covered by the existing `vinu-lib` test suite (68 passed, no
regressions — no new client tests added since the existing suite already
exercises every retry/failure branch this touches).

**3. Fixed `vinu-agent`'s LLM client — the component the whole `04`
investigation centered on** —
[`vinu-agent/vinu_agent/agent/llm.py`](../vinu-components/vinu-agent/vinu_agent/agent/llm.py),
full rewrite:
- `OpenAIChatLLM`/`AnthropicChatLLM`: `max_retries=0` now passed to the
  underlying SDK client, with an explicit retry loop replacing it —
  closing the exact gap `04-advanced-aim-1/end-to-end-complete-status.md`
  found (`max_retries=3` handed straight to the SDK, invisible to every
  caller — the `"OpenAI LLM call failed after retries"` message in the
  real replay logs was the SDK giving up silently after uncountable
  internal attempts). `retry_count` is now a real field on every
  `chat()` response.
- All four `ChatLLM` implementations now populate `result["usage"]` with
  real provider-reported token counts when available (OpenAI/DeepSeek:
  `response.usage.prompt_tokens`/`completion_tokens`; Anthropic:
  `response.usage.input_tokens`/`output_tokens`; Ollama:
  `prompt_eval_count`/`eval_count`) — previously discarded entirely by the
  `{"content":..., "tool_calls":...}`-only return contract.
- New `resolve_context_window(base_url, model)`: queries the backing
  server's `/models` endpoint for `n_ctx`/`context_length`/etc., with a
  conservative logged fallback — directly answers
  `end-to-end-complete-status.md`'s priority items 1-2 (real tokenizer
  counts now come from the provider itself when available; the model's
  real context window is now queried, not hardcoded). `AgentConfig.llm.
  context_window` (env `VINU_LLM_CONTEXT_WINDOW`) is an explicit override
  that skips the network call when set.
- 14 new tests, [`vinu-agent/tests/test_llm.py`](../vinu-components/vinu-agent/tests/test_llm.py)
  (previously zero test coverage on this file).

**4. `loop.py`'s hardcoded `max_tokens = 128000` — the specific line
`end-to-end-complete-status.md` §2.1 named as the root-cause candidate —
is gone.**
[`vinu-agent/vinu_agent/agent/loop.py`](../vinu-components/vinu-agent/vinu_agent/agent/loop.py):
`AgentLoop.max_context_tokens` now resolves, in priority order: explicit
constructor param → `llm.context_window` (set by `create_llm()` per #3
above) → a conservative `_DEFAULT_MAX_CONTEXT_TOKENS = 8000` fallback,
logged when hit. `_apply_context_layers` uses this instead of the literal
`128000`. Per-call token accounting now prefers `response["usage"]`
(real, from #3) over `_estimate_tokens`'s char/4 heuristic, falling back
only when a provider genuinely returns nothing — `token_count_source` is
tracked per call specifically so a telemetry consumer can tell which kind
of number it's looking at, never presenting an estimate with the same
confidence as a real count (same discipline as `FreshnessChecker` labeling
`STALE` data).

**5. LLM-call and tool-call telemetry wired into the actual request path**
— `loop.py`'s `run()` now records an `LLMCallRecord` after every LLM call
(success or failure, with real `retry_count`/`token_count_source`), and
`_build_result()` records one `StepRecord` per loop run with `outcome` set
to the loop's real terminal status (`completed`/`max_iterations`/`error`/
`cancelled`) — the explicit reason-code field AGENTS.md's design decision
1 called for, directly answering why `04`'s replay needed a manual trace
re-read to discover 13/22 days ended without a real decision.
`_process_tool_calls` now times and records every individual tool
invocation (both the readonly thread-pool batch and the serialized write
path) as its own `StepRecord` (`step_name="tool:<name>"`), with
`outcome` distinguishing `completed`/`timeout`/`tool_error` — this is
`AGENTS.md`'s design decision 2 (instrument tool calls, not just LLM
calls), directly aimed at `end-to-end-complete-status.md` §2.3's finding
that 9/22 replay days had tool-call flakiness independent of the
context-window bug. Wired through `session/service.py::_run_with_agent`
via `AgentLoop(..., data_root=data_root, service_name="vinu-agent")`,
reusing the same `VINU_AGENT_DATA_ROOT`-derived path already used for
sessions/facts/audit — telemetry writes to `{data_root}/telemetry.db`.
8 new tests in
[`vinu-agent/tests/test_loop.py`](../vinu-components/vinu-agent/tests/test_loop.py)
cover context-window resolution priority, real-usage-over-estimate, and
telemetry actually landing in the SQLite table for both LLM calls and
tool calls.

**Verified**: `vinu-lib/tests` — 68 passed. `vinu-agent/tests` — 303
passed (280 pre-existing + 8 loop.py + 14 llm.py + 1 from the earlier
`04` fix pass). No regressions in either suite.

## What was deliberately not done in this pass

- **`vinu-research`'s LLM call sites** (`llm.py`, `loop.py`,
  `forecast_skill.py`) already go through `vinu-lib`'s `LlmClient`/
  `AsyncLlmClient` (per the earlier codebase scan) — step 2 above already
  covers them for free. Not separately touched.
- **`vinu-initial-analysis`/`vinu-strategy`**: the earlier scan found no
  direct `vinu_lib.llm` usage confirmed in these two — not instrumented
  this pass since it wasn't confirmed they make LLM calls directly at all;
  worth confirming before assuming a gap here.
- **A dashboard or UI over the collected data** — out of scope per
  AGENTS.md; the data is queryable via `TelemetryStore.recent_llm_calls()`/
  `recent_steps()`/`summary()` directly.
- **Anthropic-provider context-window auto-resolution**: `resolve_context_
  window()` targets an OpenAI-compatible `/models` endpoint (the actual
  target — `qwen36-35B` via llama.cpp — exposes this). Anthropic's hosted
  API doesn't expose `n_ctx` this way; it falls back to the conservative
  default unless `VINU_LLM_CONTEXT_WINDOW` is set explicitly. Not fixed
  further since Anthropic isn't the deployed provider this project runs
  against.
- **Re-running the month-long replay** — explicitly deferred to
  `04-advanced-aim-1/end-to-end-complete-status.md` §3 item 6, which this
  build satisfies items 1-2 of (real tokenizer, real max_tokens source) as
  a direct consequence of steps 3-4 above. Per `AGENTS.md`'s "how to
  proceed" step 6, a short replay should confirm real telemetry rows
  before trusting the full month-long re-run.

## What to check when the next real Docker run happens

Not yet verified against the live stack (built and tested outside Docker,
same as the `04` scheduler fix). When next run:

```bash
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT model, prompt_tokens, completion_tokens, token_count_source, retry_count, outcome FROM llm_calls ORDER BY id DESC LIMIT 10;"
sqlite3 vinu-components/data/agent/telemetry.db \
  "SELECT step_name, outcome, COUNT(*) FROM steps GROUP BY step_name, outcome;"
```

Expect `token_count_source = 'provider'` for real qwen36-35B calls (not
`'estimated'` — if every row says `estimated`, the backing server isn't
returning a `usage` object, worth checking directly against
`http://host.docker.internal:8009/v1/chat/completions`). Expect `steps`
to show `agent_loop_run` outcomes matching whatever actually happened that
session, and `tool:<name>` rows for every tool call made — this table is
now the direct, queryable answer to "did today's session actually reach a
decision, and if not, what was it doing," instead of the manual raw-trace
re-read `04`'s investigation required.
