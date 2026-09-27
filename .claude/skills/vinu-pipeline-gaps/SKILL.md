---
name: vinu-pipeline-gaps
description: Use this skill when working in this trading system's vinu-components/ monorepo and the task is to find or fix real connecting gaps between services (audit-driven fixes, "why doesn't X reach Y" questions, continuing the system-wide audit series). It gives the 6-layer pipeline map, the built-vs-design decision test, and the procedure this codebase's own audit has used successfully across 20+ real fixes. Not for pure feature requests with a fully-specified design already given by the user.
---

# Vinu trading system: finding and fixing real pipeline gaps

## The source of truth

`missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-design/`
is the living audit. Two files matter most:
- `00-overview.md` — one-paragraph status per fixed item, kept current.
- `02-open-questions-strategy-and-simulation.md` — the full 26-item audit,
  each item with dated `UPDATE (...)` notes appended as things get fixed.
  Never delete or rewrite history in this file — append a dated update.

Read both before starting. They already record what's fixed, what's
still open, and — critically — *why* something wasn't fixed (a design
decision, not a bug). Don't re-investigate what's already answered there.

## The pipeline, layer by layer

```
Layer 1  vinu-screener       ScanRule/ScanMonitor (condition polling) +
                             RankerConfig/RankerRunner (factor ranking).
                             Output: ranked ticker lists, condition fires.
Layer 2  vinu-stock-price    OHLCV candles, point-in-time reads.
         vinu-news           News articles, sentiment, threat scoring.
Layer 3  vinu-tools          Indicator/factor computation library.
                             Blessed entry point: registry.apply_indicators().
                             Never deep-import vinu_tools.compute.indicators.<kind>.<kind>.
Layer 3  vinu-initial-analysis  28 "angles" computing indicator/regime/
                                 signal_evidence output per ticker, backfill
                                 + RunLog. signal_evidence angle records
                                 must-condition trigger + outcome data into
                                 vinu-research's SignalEvidenceStore over HTTP.
Layer 4  vinu-research       HypothesisRegistry (the "why" + evidence
                              lifecycle), LLM strategy generation
                              (llm_generator.py), sweep/grid backtesting
                              (sweep_grid.py -> vinu-simulator), decay
                              scanning, trade-plan authoring.
Layer 4  vinu-simulator      Executes one backtest given strategy code +
                              params. ast_guard.py sandboxes LLM-generated
                              code -- security-sensitive.
Layer 4  vinu-strategy       Deterministic weight-computation pipeline
                              (selection -> allocation -> timing -> risk)
                              for already-approved strategies, not LLM-driven.
Layer 5  vinu-portfolio      Position sizing, drawdown circuit breakers,
                              risk budget, daily allocation.
Layer 6  vinu-live           Real order execution, live-decision loop
                              (precondition check + historical evidence
                              lookup before EXECUTE), reconciliation.
Cross-cutting:
  vinu-agent      Tool-calling layer for LLM teams; in-process bridges to
                   vinu-research's stores live in broker/research_link.py;
                   scheduled workers (planner-worker, significance-worker)
                   in cli.py / agent/scheduler_workers.py are where
                   periodic/daily cross-service syncs get wired in.
  vinu-infra      Shared primitives: SQLiteBackend, ResilientClient
                   (retry/circuit-breaker HTTP), retry.py, point_in_time.py
                   (as-of clamping).
```

Data mostly flows Layer 1 -> 2 -> 3 -> 4 -> 5 -> 6, but evidence/feedback
flows backward too (Layer 6 and Layer 4 both write evidence that should
inform Layer 4's own future generation) — that backward path is where
most of the "computed, then discarded" gaps live.

## The one test that separates a buildable fix from a design question

Before touching anything, ask: **does the fix require inventing a new
schema, threshold, or matching heuristic that doesn't already exist
anywhere in the codebase?**

- **No** (both sides already exist, they're just not connected — a
  function nobody calls, a field nobody reads, a store nobody writes
  into HypothesisRegistry) → **build it.** This has been the shape of
  every successful fix in this audit series (20+ items): `apply_indicators()`
  already existed, `wilder_smooth()` already existed, `ResilientClient`'s
  `raise_on_error` was a one-line addable opt-in, `SignalEvidenceStore`
  and `HypothesisRegistry` both already existed.
- **Yes** (you'd have to decide a promotion threshold, a fuzzy-match
  rule, a new table schema, which of three redundant classifiers is
  "the" one) → **don't invent it.** Write up 2-3 concrete options with
  tradeoffs and a recommendation, and stop for the user's decision
  (see "How to propose a design decision" below). Items #1-10 and #16 in
  the audit are almost entirely this category — feature proposals, not
  bugs.

A real example of the trap: `HypothesisRegistry.add_evidence()` looks
like a generic "record evidence" function, but its promotion math
(`best_sharpe` tracking, 0.3/0.5 thresholds) is hardcoded to Sharpe-ratio
semantics. Calling it naively with a different metric (e.g. an average
return) would have silently corrupted state. **Always read what a
"generic-looking" existing function actually does with its inputs before
reusing it** — don't assume a function's name describes its full
contract.

## Procedure, in order

1. **Verify the claim, not just read it.** The audit is dated; the
   codebase keeps moving in parallel. Grep for the thing the audit says
   is missing before assuming it's still missing (a finding may already
   be fixed by unrelated work — this happened once already: item #20
   finding #4 turned out already fixed).
2. **Find the real wiring point**, not just the two endpoints. Trace one
   level further than the audit item does: who actually calls the
   producer, on what cadence, and where would the consumer naturally be
   called from that same cadence — don't invent a new schedule/service
   when an existing cycle (a scheduled worker, a route handler, a
   pipeline stage) already runs at the right cadence.
3. **Build the minimal version first.** Evidence-trail before
   auto-promotion. Strict match before fuzzy match. One new field with a
   safe default before a new table. If in doubt, the smaller, safer,
   more reversible version is right — the audit's own items #23/#3/#14
   all explicitly prefer this ("visibility before automation").
4. **Check the front AND the back.** A computed value that never reaches
   a caller (an HTTP response, a log, a return value another function
   reads) is the single most common bug this audit series has found and
   re-found — it has its own name in the audit (item #21 pattern #3,
   "compute why something failed, then discard it"). After writing the
   computation, always trace it forward to its actual consumer and
   confirm the value gets there.
5. **Fail open on cross-service/optional paths.** Every in-process
   bridge in `vinu-agent/broker/research_link.py` is documented to raise
   `ImportError` when the dependency isn't installed, with each call site
   catching exactly that (not a blanket `except Exception`, which masks
   real bugs as false negatives — this was itself a fixed bug, item #17
   finding #3). Match this contract for any new bridge code.
6. **Test through the real objects, not mocks, wherever the real objects
   are cheap** (SQLite/JSON-file-backed stores via `tmp_path` — almost
   everything in this codebase is). Mock only genuine externals (HTTP,
   LLM calls, other processes).
7. **Verify zero regressions with a real before/after delta**, not an
   assumption: run the affected test file(s), then the full service
   suite, and note the exact pass-count delta. If a suite has known
   pre-existing failures, confirm the failing test names are unchanged,
   not just that the total count didn't move (counts can coincidentally
   match while different tests broke and others started passing).
8. **Update both audit docs** — a dated `UPDATE (YYYY-MM-DD)` block in
   `02-open-questions-strategy-and-simulation.md` under the specific item
   (what was built, what was deliberately not built and why, the test
   count delta), and one line in `00-overview.md`'s status list. Check
   `grep -c "^## [0-9]" 02-open-questions...md` still equals 26 after
   editing — a misplaced edit can silently duplicate/displace a section
   heading (this has actually happened once; catch it the same way).

## How to propose a design decision (when the test above says "yes")

Don't ask an open-ended "what should I do?" — that produces vague
back-and-forth. Instead:
1. State the concrete blocking question(s) you found (ideally something
   the audit itself didn't already surface, like a hidden type mismatch
   or a hardcoded assumption in a function you were about to reuse).
2. Give 2-3 named, concrete options, each implementable as stated, with
   one real tradeoff each.
3. Give a recommendation.
4. Stop and wait. Don't start writing code for any option until one is
   picked.

## Known gotchas already discovered (don't re-derive these)

- `ResilientClient.get/post` (`vinu-infra/client.py`) swallows every
  exception into a fallback value by default — pass `raise_on_error=True`
  when the caller has its own real exception handling to reach.
- `vinu_agent/broker/research_link.py`'s in-process call sites should
  only treat `ImportError` as the "fall back to HTTP" signal — anything
  else is a real failure and must propagate.
- `Evidence.metric_kind` (added to `vinu_research/models.py`) gates
  whether `add_evidence()`'s Sharpe-specific promotion logic runs at
  all — default `"sharpe"` preserves old behavior; anything else is
  evidence-trail-only.
- Date/epoch parsing must go through `vinu_agent/tools/_date_utils.py`
  (UTC-aware) — not a local re-implementation (the old, now-removed
  per-file copies used `time.mktime`, which is local-timezone-dependent
  and was a real, silent bug).
- Server-side as-of enforcement goes through `vinu_infra/point_in_time.py`'s
  `clamp_to_as_of()` — check whether the target route already has an
  absolute-timestamp shape before wiring it in; a relative
  `days`/`hours`-back-from-now route needs a real design decision first
  (how `as_of` interacts with the relative window), not a direct port.
- Indicator computation goes through `vinu_tools.compute.registry.apply_indicators()`
  — never a deep import of an individual indicator module.
