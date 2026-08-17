---
name: phase-5-implement-test
status: built -- Phase 5 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 5 -- Implementation record

Built 2026-08-11, directly following Phase 4 in the same session.

## The most consequential finding this session: TradePlanOrchestrator was never actually running

Investigating `01-plan.md` item 4 (batching -- already done, confirmed by
reading `cycle()` directly: it fetches all symbols' prices in one batched
call before its per-plan loop, no work needed) led to reading
`entrypoint.sh` and `cli.py` together, which surfaced something bigger:
**`vinu-live`'s deployed container only ever started ONE of its three
real worker loops.** `vinu-live-worker` (-> `worker_main` ->
`LiveScheduler.cycle()`, a *separate* portfolio-target rebalancer) was
the only thing `entrypoint.sh` ran automatically. `trade_plan_worker_main`
(`TradePlanOrchestrator.cycle()` -- the actual entry/invalidation-exit/
contingency authority `mermaid-explanation.md` calls "sole authority on
live-position close/hold") and `feedback_worker_main`
(`FeedbackLoopWorker.cycle()`) both had complete, real, tested
`while True: cycle(); sleep()` implementations that **nothing ever
invoked**. This is the same "wiring gap, not a design gap" shape as
`vinu-portfolio`'s drawdown-monitor fix (documented precedent in
`skills/live-safety/SKILL.md`, Stage 3) and Phase 4's endpoint finding --
found here by reading the deployment script directly rather than trusting
the mermaid doc's "already real, running, sole authority" framing.
**Fixed**: `entrypoint.sh` now also starts `vinu-live trade-plan-worker`
and `vinu-live feedback-worker` alongside the existing portfolio worker
and the API server -- four processes, matching `vinu-portfolio`'s own
proven multi-process pattern.

## The HypothesisRegistry write already existed -- just not where Phase 5 expected

`01-plan.md` item 1 said `feedback_loop.py` never writes to
`HypothesisRegistry`. True, but reading `vinu-agent`'s `broker/debrief.py`
directly found a SEPARATE, already-built, already-correct mechanism
(`PositionCloseDetector`) that already does exactly this -- via a
different detection path (Alpaca fill-history replay, triggered per
conversational session turn in `vinu-agent`, not vinu-live's own book).
Added the write to `feedback_loop.py` anyway (Phase 5 explicitly asked
for it, and it closes a real gap: `debrief.py`'s path only fires when a
human happens to be chatting with the agent, not continuously) --
**deliberately not deduplicated against `debrief.py`'s writes**, see
Design deviations below for why.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-live/entrypoint.sh` | modified | Now starts `trade-plan-worker` and `feedback-worker` alongside the existing portfolio worker and API server -- the critical fix. |
| `vinu-components/vinu-live/vinu_live/feedback_loop.py` | modified | `_process_closed_position` gains two new best-effort writes (after the existing three, after `mark_feedback_processed`): `_record_hypothesis_evidence` (GET `/research/hypotheses?symbol=`, POST `/research/hypotheses/{id}/evidence` for each active-status hypothesis, `metric="realized_return_pct"`) and `_write_ticker_ledger_closeout` (POST to vinu-agent's new cross-container endpoint below). |
| `vinu-components/vinu-live/tests/test_feedback_loop.py` | modified | `_make_worker` now mocks `_http.get` (empty hypotheses by default) so existing POST-count assertions stay meaningful. 4 new tests: hypothesis-evidence write, active-status filtering, TickerLedger row, and the audit-write-failure-doesn't-block-or-reverse-the-close ordering test. |
| `vinu-components/vinu-agent/vinu_agent/server/routes_ticker_ledger.py` | new | `POST /agent/ticker-ledger/event` -- the cross-container front door onto Phase 0's `TickerLedgerStore`, needed because vinu-live runs in a separate container with no filesystem/in-process access to vinu-agent's store. First real cross-service `TickerLedger` writer. |
| `vinu-components/vinu-agent/vinu_agent/server/app.py` | modified | New router wired in, following the existing `_get_service` pattern. |
| `vinu-components/vinu-agent/tests/test_routes_ticker_ledger.py` | new | 3 tests. |
| `vinu-components/vinu-live/vinu_live/trade_plan/rebalance_intake.py` | new | `RebalanceRequestQueue` -- thread-safe, in-memory, one-pending-request-per-symbol. |
| `vinu-components/vinu-live/vinu_live/trade_plan/orchestrator.py` | modified | `submit_rebalance_request()`, `_evaluate_rebalance_request()` (checked strictly AFTER the plan's own invalidation/contingency rules, can decline on a real unrealized gain > 5% (provisional), otherwise reduces via the same breaker-checked order path `_apply_contingency` uses). New `on_shock_event(symbol)` -- off-cycle, per-symbol-debounced (60s, provisional) evaluation reusing `_evaluate_open_position`/`_maybe_enter` unmodified. |
| `vinu-components/vinu-live/tests/test_trade_plan_orchestrator.py` | modified | 6 new rebalance-intake tests (priority-over-invalidation, declined-on-gain, honored, breaker-blocked, consumed-once, no-request-baseline) + 6 new shock-trigger tests (fires for open position, can enter new position, debounced, fires again after window, per-symbol not global, no matching plan). |
| `vinu-components/vinu-live/tests/test_rebalance_intake.py` | new | 6 tests for the queue in isolation. |

## Design deviations from `01-plan.md`/`02-guard-rail.md`, and why

- **The rebalance-request intake has no HTTP route yet, on purpose.**
  `TradePlanOrchestrator.cycle()` runs inside a SEPARATE OS process
  (`trade-plan-worker`, now actually started -- see above) from the API
  server (`vinu-live serve`) per `entrypoint.sh`'s own multi-process
  design. An in-memory `RebalanceRequestQueue` on one process's
  orchestrator instance is invisible to the other process entirely --
  exposing an HTTP route onto it today would silently do nothing in the
  real deployment (accept requests into a queue nothing ever reads),
  which is worse than not building it. There is also still no real
  caller: Phase 2 built funding, not a rebalancer that unwinds existing
  positions to free capital (confirmed again this phase, matching Phase
  3's `rebalance_guard.py` finding). Built and fully tested at the
  same-process level (proving the advisory-only fold-in behavior the
  guard rail actually cares about), matching the exact precedent
  `rebalance_guard.py` set in Phase 3: ready, correct, tested, not yet
  wired to a caller/transport that doesn't exist. Cross-process
  persistence (a shared table in `trade_plan_book.db`, most likely) is
  real follow-up work for whenever a real caller gets built, not decided
  here.
- **`HypothesisRegistry` evidence duplication between `debrief.py` and
  `feedback_loop.py` was not deduplicated.** Both can now fire for the
  same real close (`debrief.py` when a chat session happens to be active
  around that time; `feedback_loop.py` continuously, now that its worker
  actually runs). Not resolved because: (a) `add_evidence` appends to a
  list and updates `best_sharpe` via `max()`, not a running sum -- a
  duplicate is redundant, not silently corrupting; (b) the two writes use
  different `metric` names (`realized_pnl` dollar amount vs.
  `realized_return_pct` percentage) so a reader can tell them apart, not
  mistake them for an exact duplicate; (c) real cross-service
  deduplication (e.g. a shared idempotency key on the close event) is
  more design work than this phase's stated scope, and inventing one
  without a documented real incident to fix would be scope creep. Flagged
  explicitly as a known, accepted follow-up, not silently ignored.
- **`ShadowEvaluator` was NOT added to the entrypoint.sh fix**, even
  though it has the same "built, not scheduled" shape as the two workers
  that were fixed. Unlike `trade_plan_worker_main`/`feedback_worker_main`,
  no continuous-loop CLI subcommand exists for it yet (only a single-shot
  `shadow-evaluate`) -- adding one is new design work, not flipping on an
  already-complete implementation, and stays out of scope for both Phase
  4 (which said so explicitly) and this phase.

## Test results

```
vinu-live:   144 passed (full suite; 6 + 6 + 4 + 6 = 22 new tests across 4 files)
vinu-agent:  515 passed (full suite; 3 new route tests)
```

No regressions in either package's full suite.

## Known follow-ups (not blocking, not silently dropped)

- **Cross-process wiring for the rebalance-request intake** -- needs a
  real caller (Phase 2's rebalancer, not yet built) and a decision on
  shared persistence before an HTTP route can safely be added.
- **`ShadowEvaluator` still has no scheduled caller** -- unchanged from
  Phase 4's own finding, now doubly confirmed not to be this phase's
  scope either.
- **`_REBALANCE_PROTECT_GAIN_PCT` (5%) and `_SHOCK_DEBOUNCE_SEC` (60s)**
  are first-pass, defensible, explicitly-flagged-provisional defaults,
  same category as every other untuned threshold across this build.
- **The `debrief.py`/`feedback_loop.py` HypothesisRegistry overlap**
  should be revisited if it ever produces a real, observed confusion in
  practice (e.g. a human reviewing evidence history finds the duplication
  actually misleading) -- not preemptively engineered around here.
