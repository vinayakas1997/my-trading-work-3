---
name: observability-telemetry-layer
status: steps-1-4-implemented
purpose: single source of truth for why this folder exists and what it is building — a shared, cross-service instrumentation layer for vinu-components (LLM token/retry/latency tracking, per-step timing, data-volume/storage tracking) — so any agent picking this up cold understands the problem, the constraints, and how to proceed without re-deriving context from 04-advanced-aim-1. Companion to status.md, which is the build log for what's actually landed (steps 1-4, plus a first pass at step 5) — this file stays the design/why, status.md is the record of what happened.
---

# Observability & Telemetry Layer — Why and How to Proceed

## Why this folder exists

`04-advanced-aim-1/end-to-end-complete-status.md` ran a real 22-day
live-agent replay against the actual Docker stack and found the agent
placed **zero trades across the entire month** — not because it decided
not to trade, but because 13 of 22 days' ReAct loops ended without ever
reaching a final decision, and one day hard-failed with `Context size has
been exceeded`. That specific bug was found the hard way: by manually
re-reading raw `thinking.json` tool-call traces line by line, because
nothing in the system was actually measuring what was going on inside the
loop while it ran (`04-advanced-aim-1/end-to-end-complete-status.md`
§2.1, §2.6).

The root-cause candidate that investigation surfaced is concrete and
already located in the code:

- `vinu-components/vinu-agent/vinu_agent/agent/loop.py:305` hardcodes
  `max_tokens = 128000` as the context budget the loop compacts against.
- The real backing model (`qwen36-35B`) has a **32,000-token** context
  window (confirmed via `curl http://localhost:8009/v1/models` →
  `"n_ctx": 32000`) — a 4x mismatch.
- The token estimate feeding that budget check isn't a real tokenizer —
  it's `_estimate_tokens` at `loop.py:31-32`, a flat `len(text) / 4.0`
  character-count heuristic, used at `loop.py:116/119/304`.

This folder's job is **not** to fix that one constant. It's to build the
instrumentation layer that would have surfaced this bug — and the other
seven problems in that same status file's §2 — from real measurements as
they happened, instead of from a forensic trace re-read after the fact.
That's the actual ask: token counts sent/received per LLM call, API
timing, retry counts, and data-volume/storage stored per pipeline step,
across every service, not just `vinu-agent`.

## What this folder is for

A design-then-build folder for one thing: a shared instrumentation module
that any `vinu-*` service can wrap its LLM calls and pipeline steps with,
persisting real per-call and per-step measurements somewhere queryable —
not a new standalone service, not a dashboard project (yet), not a fix
for the tokenizer bug itself (that's downstream, tracked in
`04-advanced-aim-1/end-to-end-complete-status.md` §3, items 1-2, and
happens to get largely fixed as a side effect of wiring `vinu-agent` onto
this layer correctly).

## What already exists — don't rebuild this

The codebase is not starting from zero. Confirmed live in the repo (all
paths verified to exist, not recalled from memory):

- **`vinu-components/vinu-infra`** is a shared package already installed by
  most services (`vinu-news`, `vinu-research`, `vinu-initial-analysis`,
  `vinu-strategy` confirmed — each `COPY`s it in and `pip install -e`s it
  in their Dockerfile). This is where the new instrumentation module
  belongs, not a new package.
- **`vinu-infra/llm/client.py`** and **`vinu-infra/llm/client_async.py`**
  already implement `LlmClient.chat_json` / `AsyncLlmClient.chat_json`
  with manual retry-with-backoff over multiple candidate URLs, and already
  log every call to `data/llm_calls.jsonl` (tokens, cost, duration,
  success) via an internal `_log_llm_call`.
- **`vinu-infra/llm/cost.py`** has a `CostTracker` /
  `get_global_cost_tracker()` singleton — in-memory only, not persisted,
  not queryable across a run.
- **`vinu-infra/sqlite.py`** provides a shared `SQLiteBackend` base class
  (thread-local connections, WAL mode) and **`vinu-infra/db.py`** provides
  migration helpers (`migrate_schema`, `PRAGMA user_version`) — most
  services already have their own SQLite DB built on this base. This is
  the natural place to add a metrics table, not a new database engine.
- **`vinu-infra/retry.py`** has a generic `retry_on_transient` decorator,
  currently used for plain HTTP, not LLM-specific.
- **No Prometheus, OpenTelemetry, or structlog anywhere in the repo** —
  confirmed by grep, zero matches. Only stdlib `logging` per module. This
  folder does not need to integrate with an existing metrics stack because
  there isn't one.

## The one gap that matters most: `vinu-agent` bypasses all of the above

`vinu-agent/vinu_agent/agent/llm.py` does **not** use `vinu-infra`'s LLM
client. It has its own `OpenAIChatLLM.chat()` (lines 18-54) that hands
`max_retries=3` straight to the raw `openai` SDK client (line 24) — which
means retry attempts happen *inside the SDK*, invisible to any wrapping
code. The error message seen in the real replay logs
(`"OpenAI LLM call failed after retries: ..."`, line 39) is the SDK
giving up silently after 3 internal attempts nobody outside it could
count. `OllamaChatLLM` (lines 130-166) has its own separate manual retry
loop. Three different retry implementations exist project-wide, and the
one on the component that actually failed during the real replay is the
one with zero visibility into its own retry count.

**This means retry-count instrumentation cannot be bolted on from
outside `vinu-agent`'s LLM call site — it requires either switching that
call path onto the shared `vinu-infra` client, or setting `max_retries=0`
on the SDK client and doing retries explicitly so they're observable.**
This is not optional scope creep; without it, "LLM retry how many times"
is unanswerable for the exact component that needs the answer most.

## Design decisions carried in from `04`'s findings — not re-litigated per file below

These came out of reviewing `04-advanced-aim-1/end-to-end-complete-status.md`
and its `bugs-fixes-while-test/` folder in full before starting this one.
Stated once here:

1. **Every step/call record needs an explicit outcome/termination-reason
   field, not just numeric metrics.** Three separate bugs in `04` share
   one shape: something silently produced a plausible-looking but wrong
   result instead of erroring — `write_day()` falling back to an earlier
   planning message and presenting it as the day's final decision
   (`bugs-fixes-while-test/replay-agent-never-executed-a-trade.md`), the
   replay harness reporting a false `exit code 0` because `tail` swallowed
   a real crash (`bugs-fixes-while-test/replay-harness-poll-timeout-crash.md`),
   and a summary table quoting stale test counts that looked authoritative
   (`bugs-fixes-while-test/bug-count-mismatch-in-implementation-agents.md`,
   `bugs-fixes-while-test/stale-test-counts-in-e2e-agents.md`). A layer
   that only logs "tokens sent/received" will not catch this class of bug.
   Every step record needs a reason code: completed-with-decision,
   hit-iteration-limit, hit-context-overflow, tool-error-aborted,
   etc. — logged even when nothing crashed.
2. **Instrument tool calls, not just LLM calls.**
   `04-advanced-aim-1/end-to-end-complete-status.md` §2.3 found
   features-api/fundamentals flakiness on 9 of 22 replay days (41%),
   independent of the context-window bug, each occurrence burning
   iterations on manual recompute. A layer that only wraps the LLM client
   explains the one `Context size has been exceeded` day and stays silent
   on the other eight days that likely died from iteration-budget
   exhaustion caused by tool-call retries.
3. **Persist to SQLite via the existing `vinu-infra/sqlite.py` base, not a
   new store**, mirroring the pattern every other service already uses for
   its own DB. Keep JSONL as a secondary append log (cheap, tailable) —
   `vinu-infra/llm/client.py` already does this for LLM calls; extend the
   pattern, don't replace it.
4. **Don't let this become a third hand-maintained summary that drifts.**
   Two of `04`'s own bugs were exactly that: a rollup table quoting numbers
   that no longer matched the detailed status file underneath it. If
   `end-to-end-complete-status.md`-style narrative rollups get written
   again once this layer exists, they should be generated from the
   metrics DB, not hand-copied from it.
5. **Capture container-level restart/OOM events alongside the rest**,
   cheaply, while already touching this. `04`'s `agent-api` mid-replay
   restart (`bugs-fixes-while-test/agent-api-container-restart-mid-attempt.md`)
   was never root-caused (OOM ruled out via `docker stats`, real cause
   unknown) — the next time the month-long replay runs
   (`04-advanced-aim-1/end-to-end-complete-status.md` §3 item 6), this is
   the mechanism that catches it with real evidence if it recurs.

## How to proceed

1. ~~Design the shared schema first~~ **Done** — `LLMCallRecord`/
   `StepRecord` + `TelemetryStore(SQLiteBackend)` in
   `vinu-components/vinu-infra/telemetry.py`. See `status.md`.
2. ~~Wire it into `vinu-infra/llm/client.py` / `client_async.py`~~ **Done.**
3. ~~Fix `vinu-agent/vinu_agent/agent/llm.py`~~ **Done** — explicit retry
   loops (SDK `max_retries=0`), real provider `usage` populated on every
   `ChatLLM` implementation, `resolve_context_window()` added.
   `04-advanced-aim-1/end-to-end-complete-status.md` §3 items 1-2 (real
   tokenizer, real `max_tokens` sourced from the model) resolved as a
   direct consequence, per `status.md`.
4. ~~Add the SQLite table~~ **Done**, via `TelemetryStore` (step 1).
5. Wrap tool calls (`get_features`, `get_fundamentals`, etc.) with the
   same `StepRecord` schema — not just the LLM client. **First pass done**
   (`loop.py::_process_tool_calls` now records every tool call); not yet
   extended to `vinu-research`/`vinu-initial-analysis`'s own tool/API call
   sites outside the agent loop.
6. Only after 1-5: re-run a short (few-day, not full-month) replay to
   confirm records are actually being written with real numbers, before
   trusting it for the full month-long re-run
   `04-advanced-aim-1/end-to-end-complete-status.md` §3 item 6 calls for.
   **Not yet done** — this build was made and unit-tested outside Docker.
   The runbook for this step is [`end-to-end-test.md`](end-to-end-test.md)
   — do not improvise this check ad hoc; that file has the exact queries
   and pass/fail criteria per `04` step. Any bug found while running it
   goes in [`bugs-fixes-while-test/`](bugs-fixes-while-test/AGENTS.md), one
   file per issue, same convention `04` already established.

## What "done" looks like

Every LLM call across every service that uses `vinu-infra` (and, after step
3 above, `vinu-agent` specifically) produces a queryable record with real
tokenizer-based counts, real retry counts, latency, and an explicit
outcome reason — queryable via SQL against one table, not by re-reading
raw JSON traces by hand the way `04`'s investigation had to.

## What this folder does not cover

- A dashboard or UI over the collected metrics — out of scope until the
  collection layer itself exists and has been validated against a real
  run.
- Re-running the full 22-day replay to validate this layer — a short
  replay is enough to confirm records are being written correctly (see
  step 6 above); the full month-long re-run belongs to
  `04-advanced-aim-1/end-to-end-complete-status.md` §3 item 6, once the
  tokenizer/context-budget fix has also landed.
- Root-causing *why* 13/22 days ended without a decision, or *why*
  `agent-api` restarted mid-replay — this folder builds the instrument
  that will surface the evidence next time; it does not itself diagnose
  those two still-open findings.

## Related documents

- [`status.md`](status.md) — the build log: what actually landed for
  steps 1-5 above, file:line, test counts.
- [`observed-rates-and-build-timings.md`](observed-rates-and-build-timings.md)
  — real, measured LLM call latency (`vinu-research` and `vinu-news`
  separately), FinBERT scoring throughput, and per-service Docker build
  timings from actually running this against the live stack on
  2026-08-04 — not estimates.
- [`end-to-end-test.md`](end-to-end-test.md) — the runbook for step 6,
  and [`bugs-fixes-while-test/`](bugs-fixes-while-test/AGENTS.md) — where
  findings from running it get written up.
- [`../04-advanced-aim-1/end-to-end-complete-status.md`](../04-advanced-aim-1/end-to-end-complete-status.md)
  — the real end-to-end run this folder's entire motivation comes from.
  §1 is what was verified working; §2 is every problem found, with root
  causes where known; §3 is the prioritized remaining work list this
  folder's step 3 partially resolves.
- [`../04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/`](../04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/AGENTS.md)
  — one file per bug found during that run; several are cited by name
  above and are worth reading in full before writing the schema, since
  each one describes a real failure shape this layer needs to be able to
  represent, not a hypothetical one.
