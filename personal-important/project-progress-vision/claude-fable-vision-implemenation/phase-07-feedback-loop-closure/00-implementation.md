# Phase 7: Feedback-Loop Closure (final phase)

**Status:** COMPLETED
**Started:** 2026-07-27
**Completed:** 2026-07-27
**Source doc:** ../claude-fable-vision/phase-07-feedback-loop-closure.md
**Depends on:** Phase 2 (personality angles), Phase 4 (forecast/plan authoring), Phase 6 (execution)
**Blocks:** none — final phase

## What It Delivers

The write-back path from Phase 6's realized trade outcomes into Phase 2's personality stats
and Phase 4's calibration tracking, plus population of `vinu-initial-analysis`'s
`pnl_attribution` angle from real execution data. Not a live re-decision loop — every write
here is consumed at the next research cycle or the next `approve_trade_plan` call, never fed
back into `TradePlanOrchestrator` or any in-trade action.

## Discoveries made before implementation

1. **`pnl_attribution` did not exist as code anywhere**, despite every planning doc (including
   the governing `my-learning/new-direction-for-the-project.md`) describing it as an "existing
   angle, currently dormant." Built from scratch — the third time this vision project's
   planning docs described something as already-existing that needed building (after Phase 4's
   broken `_LLM` import and Phase 6's unwired book/breaker).
2. **`vinu_research/decay.py` (the source doc's "existing decay_monitoring/decay-scan") is the
   strategy-decay mechanism (IC/Sharpe), not a forecast-calibration one.** Phase 4 already built
   the real analog (`calibration.py`, `forecast_skill.py`'s scoring functions) — but nothing
   persisted a `CalibrationEntry`, and the approve route built a fresh, empty tracker on every
   call. Phase 7's actual job was persistence + a write path into that already-built machinery.
3. **A closed `Position` had no link back to the `TradePlan` artifact that opened it.** Fixed by
   adding `artifact_id` to `open_positions`/`closed_positions` and threading it through
   `TradePlanOrchestrator._maybe_enter`.
4. **`AngleRunner.run()` already supported a targeted `angle_names` subset** — just not exposed
   over HTTP. Threaded through `POST /run/{ticker}` → `InitialAnalysisService.run_analysis` →
   `AngleRunner.run`. One wrinkle: `has_existing_run`'s dedup check skips a re-run whose
   `(symbol, angle_name)` already has *any* completed run when `from_ts`/`to_ts` are both
   `None` — every trigger passes a fresh `to_ts=<now>` to actually take effect.

## Open Questions Resolved

1. **`pnl_attribution` is push-fed, not runner-driven.** Its natural input (execution
   fills/closed positions) doesn't fit the runner's `compute(symbol, bars, news, ...)`
   contract. It has a normal `angles/pnl_attribution/` folder (discoverable, has
   `compute.py`/`spec.yaml`) so a generic `/run/{ticker}` sweep doesn't error — that path is a
   documented no-op (`status: "push_fed_not_runner_driven"`) — but real population is
   `AngleStorage.write()` called directly from `pnl_attribution_ingest.py`, triggered by
   `POST /pnl-attribution/{symbol}/record`.
2. **The coordinating job lives in `vinu-live`** (`feedback_loop.py`'s `FeedbackLoopWorker`),
   not vinu-research or vinu-initial-analysis, because it holds the source-of-truth
   closed-position data and `shadow_evaluator.py` already established this exact job shape
   (poll local/owned state, push updates to other services over HTTP).
3. **Realized return for calibration scoring is the underlying's price return
   (`(close_price - avg_entry) / avg_entry`), not sign-flipped by position side.** A short
   position that profited from a price decline still reports a negative return — matching what
   `Forecast.direction`/`compute_directional_error` actually score (the underlying's move, not
   the position's P&L sign). See `feedback_loop._realized_return_pct`.
4. **A bug found via a route-level test, not a unit test**: `aggregate_pnl_attribution`
   originally stored `closed_positions` as a raw list-of-dicts DataFrame column. Parquet
   round-trips that as a numpy object array, which FastAPI's JSON encoder can't serialize —
   `GET /angle/pnl_attribution/{symbol}` returned a 422. Fixed by storing it as a JSON string
   (`closed_positions_json`), matching how `vinu-research`'s `Artifact.universe` already
   handles list-valued columns. This is exactly why the test plan called for a route-level test
   in addition to the pure-function unit tests — the bug was invisible below the HTTP boundary.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_live/book/schema.py` | vinu-live | modify — `Position.artifact_id` |
| `vinu_live/book/positions.py` | vinu-live | modify — migration (`artifact_id`, `feedback_processed_at`), `list_closed_positions`, `mark_feedback_processed` |
| `vinu_live/trade_plan/orchestrator.py` | vinu-live | modify — passes `artifact_id` into `open_position` |
| `vinu_live/feedback_loop.py` | vinu-live | create — `FeedbackLoopWorker` |
| `vinu_live/cli.py`, `vinu_live/server/app.py`, `vinu_live/config.py` | vinu-live | modify — `feedback-cycle`/`feedback-worker` wiring |
| `vinu_research/storage/strategy_store.py` | vinu-research | modify — `calibration_entries` table |
| `vinu_research/calibration.py` | vinu-research | modify — `CalibrationTracker.load_entries` |
| `vinu_research/trade_plan_authoring.py` | vinu-research | modify — `record_realized_outcome`, `load_calibration_tracker`; `approve_trade_plan` now rebuilds from persisted entries |
| `vinu_research/server/routes_trade_plan.py` | vinu-research | modify — fixed approve route, added `POST .../record-outcome` |
| `vinu_initial_analysis/angles/pnl_attribution/` | vinu-initial-analysis | create — `compute.py`, `spec.yaml` |
| `vinu_initial_analysis/pnl_attribution_ingest.py` | vinu-initial-analysis | create |
| `vinu_initial_analysis/server/routes_read.py`, `service.py`, `api.py` | vinu-initial-analysis | modify — record endpoint, `angle_names` passthrough |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-book-artifact-link.md` | Link closed positions back to their trade-plan artifact | DONE |
| 2 | `02-task-calibration-persistence.md` | Persist and reload calibration entries; fix approve gate | DONE |
| 3 | `03-task-pnl-attribution-angle.md` | Push-fed `pnl_attribution` angle + targeted Phase 2 refresh | DONE |
| 4 | `04-task-feedback-loop-worker.md` | `FeedbackLoopWorker` tying all three together | DONE |

## Dependencies Met

- [x] Phase 2 completed (personality angles this phase refreshes)
- [x] Phase 4 completed (calibration machinery this phase persists into)
- [x] Phase 6 completed (closed positions this phase reads from)

## Non-Negotiable Rule Check (AGENTS.md Rule 10)

No LLM call anywhere in this phase. `FeedbackLoopWorker` only reads its own local book and
issues plain HTTP POSTs; `record_realized_outcome`/`aggregate_pnl_attribution` are pure
scoring/aggregation functions. Confirmed structurally in `test_feedback_loop.py`'s
`test_never_imports_orchestrator` — this phase has no dependency on the live-trading decision
path at all, only on its already-written output (closed positions).

## What Still Doesn't Work After This Phase (by design, per the source doc)

Calibration entries only accumulate from real closed positions with a real `artifact_id` —
which only exist once Phase 6 actually runs against a live/paper broker. `approve_trade_plan`
is correctly still fail-closed for any plan with no realized history yet; this phase closes the
mechanism, not the cold-start problem of needing real trades before the first plan can ever be
approved. That's outside this vision's scope, same as the source doc's own "What still won't
work" section notes.
