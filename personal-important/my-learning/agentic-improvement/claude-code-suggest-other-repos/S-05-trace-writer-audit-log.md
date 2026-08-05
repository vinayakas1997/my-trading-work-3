# S-05: A Real Trace/Audit Log, Not One Reasoning String Per Iteration

## What It Is

Today, the only record of "what the agent was thinking" is
`IterationRecord.reasoning` (`models.py`) — one string per iteration, populated
from either the LLM's `best.reasoning` (generation/refinement) or the diagnosis
LLM call. Everything else — the exact prompts sent, every LLM call made
(generate, refine, critic, diagnose, characterize, reflect, validate — up to 6-7
distinct LLM calls can happen in a single iteration now, after P2/P4), tool calls
to `ResearchTools`, timing — is either not captured at all, or scattered across
`LOG.info`/`LOG.warning` calls that aren't structured or queryable.

Vibe-Trading's `TraceWriter` (`agent/src/agent/trace.py`) is a dedicated JSONL
append-and-flush log: every LLM call, tool call, and tool result is its own
record. Large payloads (prompts, tool results) are offloaded to sidecar files past
a size threshold (`TOOL_RESULT_OFFLOAD_THRESHOLD=50_000` chars,
`trace.py:38-46,159-182`) with a short inline preview kept in the JSONL, so reading
the trace stays cheap even when individual calls are huge.

## Why It's Required

The P1–P4 additions turned each iteration from "one LLM call" into "up to six LLM
calls with several branching decision points" (diagnose only if 0 trades,
reflect only if sharpe<0.1 and trades<5, characterize once per run, validate once
per run). When something goes wrong — a bad pivot decision, an LLM hallucinating a
diagnosis, an unexpectedly expensive run — `IterationRecord.reasoning` alone
cannot answer "which of the 6 calls said what, in what order, with what inputs."
This is exactly the debugging gap **S-01 through S-04 all eventually run into**:
every one of them benefits from being able to replay what actually happened.

## Impact

- **If unfixed:** debugging any of the P2–P4 features (diagnosis quality, pivot
  timing, characterization accuracy) means re-running with elevated logging and
  hoping to reproduce the issue — there's no persistent record to go back to.
- **If fixed:** every run has a complete, replayable trace — directly useful for
  auditing why a hypothesis got rejected (pairs naturally with S-02), for spotting
  when `_reflect()` pivots too eagerly (informs S-11's confidence scoring), and for
  cost/latency analysis of the now much heavier per-iteration LLM call volume.

## How to Use Effectively

1. Start narrow: add a `TraceWriter`-equivalent that logs one JSONL line per LLM
   call already made in `loop.py` and `llm.py` — `{timestamp, call_type, symbol,
   iteration, system_prompt_hash, response_summary, latency_ms}`. Don't try to
   capture full prompt/response text inline; hash or truncate, matching Vibe-
   Trading's offload-large-payloads approach.
2. Write to `<data_root>/traces/<run_id>.jsonl` (one file per run, not one giant
   shared file) — keeps it naturally scoped and avoids the concurrency problems
   described in S-03.
3. This is *additive* — it doesn't replace `IterationRecord.reasoning`, which stays
   the "headline" reasoning for quick display; the trace is the full audit trail
   underneath it for when the headline isn't enough.
4. Once this exists, it becomes the natural place to log **S-11**'s confidence
   scores and **S-10**'s tool-call records if/when those land — build this first,
   since several other suggestions want a place to write structured events.

## Implementation Hint — Where This Fits Today

**Entry points:** every method on `ResearchLlmClient` (`llm.py`) —
`chat_json`, `diagnose_failure`, `characterize_stock`, `suggest_pivot`,
`validate_idea` — plus `llm_generator.py`'s `_generate_one`/`_refine_one`. All of
them are thin wrappers already funneling through `self._client.chat_json(...)` or
similar — a trace log can wrap at that single choke point rather than
instrumenting each of the 7 call sites individually.

**Why this is feasible right now:**
- `self._run_id` already exists on `StrategyResearchLoop` (threaded through by
  R-C) — trace files can be named `<run_id>.jsonl` immediately, no new ID
  scheme to invent.
- `ResearchConfig.data_root` (`config.py:55`) already exists and is already the
  root for other persistent state (SQLite DBs) — `data_root / "traces"` is a
  one-line addition, not a new configuration concept.
- `debug_timer` (imported in `loop.py` from `vinu_infra.debug`, already wrapping
  every generation/backtest/walk-forward/stress-test step) shows this codebase
  already has a lightweight instrumentation convention — a trace writer should
  follow that same style/import pattern rather than introducing an unrelated
  logging framework.

**Cheapest correct first cut:** wrap `ResearchLlmClient.chat_json()` itself (the
one function nearly everything else calls through) to append one JSONL line per
call — `{run_id, call_type inferred from the system prompt constant used,
timestamp, latency_ms, response_keys}` — before touching any of the 7 individual
call sites. That single wrap point captures ~90% of the value for ~10% of the
integration work.

## Potential Bugs to Watch For While Testing

- **Concurrent writes from `asyncio.gather`.** `llm_generator.py`'s `generate()`
  fans out `n_candidates` concurrent `_generate_one()` calls via `asyncio.gather`
  — if each one appends a JSONL line through the same file handle without
  synchronization, concurrent writes can interleave mid-line and corrupt the
  file (a reader sees two half-lines merged into one invalid JSON line). Test
  with `n_candidates > 1` specifically, not just a single sequential call — the
  bug won't show up in a single-candidate test.
- **Sidecar offload boundary conditions.** Test a prompt/response that lands
  exactly at `TOOL_RESULT_OFFLOAD_THRESHOLD` (if you copy that constant's value)
  and one just over it — off-by-one errors in size-based branching are common
  and easy to miss with only "clearly small" and "clearly huge" test cases.
  Also test that truncating for the inline preview doesn't cut in the middle of
  a multi-byte UTF-8 character if any prompt content is non-ASCII.
- **Unbounded disk growth has no test today.** There's no retention/cleanup
  logic described here — write a test (or at least a documented manual check)
  confirming the trace directory's growth rate is understood, even if cleanup
  itself is out of scope for the first version.
- **Don't let error text leak secrets into the trace.** If any traced
  prompt/response ever includes a raw provider error message (e.g. a failed API
  call's exception text), test that it doesn't end up persisted verbatim if that
  error text could contain an API key or token — apply the same kind of
  redaction Vibe-Trading's `_redact_provider_error` does before persisting, not
  just before logging to console.
