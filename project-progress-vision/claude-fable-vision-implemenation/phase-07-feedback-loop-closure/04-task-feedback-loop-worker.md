# Task 4: Feedback-Loop Worker

**Status:** DONE

## Purpose

Tie Tasks 1–3 together into the actual coordinating job: for every closed position vinu-live
hasn't fed back yet, score its realized outcome against Phase 4's forecast, push it into
Phase 4's calibration and Phase 2's `pnl_attribution`/personality angles, and mark it processed.

## Approach

- `FeedbackLoopWorker` lives in `vinu-live` (`feedback_loop.py`), not vinu-research or
  vinu-initial-analysis — see `00-implementation.md`'s Open Question #2 for why. Mirrors
  `shadow_evaluator.py`'s shape (poll local/owned state, push over HTTP) exactly, and
  `TradePlanOrchestrator`'s CLI/HTTP wiring pattern (`feedback-cycle`/`feedback-worker`
  subcommands, `POST /feedback/cycle`).
- `cycle()`: `list_closed_positions(unprocessed_only=True)` → for each, compute
  `_realized_return_pct` (the underlying's raw price return — see `00-implementation.md`'s
  Open Question #3 for why it's not sign-flipped by side), POST to vinu-research's
  record-outcome endpoint, POST the closed position to vinu-initial-analysis's pnl-attribution
  endpoint, POST a targeted `/run/{symbol}?angle_names=shock_personality,shock_clustering` with
  a fresh `to_ts`, then `mark_feedback_processed` regardless of whether the outbound calls
  succeeded — a failed write-back is logged, not retried indefinitely, matching "never blocks
  live trading."
- Structurally verified to have no dependency on `trade_plan/orchestrator.py` — it never
  triggers any in-trade action, only ever writes to storage consumed at the next cycle.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/feedback_loop.py` | — | Created |
| `vinu_live/cli.py` | — | `feedback-cycle`/`feedback-worker` subcommands |
| `vinu_live/server/app.py` | — | `POST /feedback/cycle` |
| `vinu_live/config.py` | — | `feedback_worker_interval_sec` |

## Verification

- [x] Tests pass (`tests/test_feedback_loop.py`, 12 tests — realized-return computation for long/short, full-cycle processing, idempotent re-marking, outbound-failure resilience, targeted angle refresh with a fresh `to_ts`, and the no-orchestrator-dependency check)
- [x] Manual: `create_app()` route listing confirms `/feedback/cycle` registered alongside Phase 6's routes
- [x] No runtime LLM call introduced outside `vinu-research`
