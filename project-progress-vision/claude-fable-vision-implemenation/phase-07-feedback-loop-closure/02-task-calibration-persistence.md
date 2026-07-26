# Task 2: Calibration Persistence

**Status:** DONE

## Purpose

Persist `CalibrationEntry` rows so Phase 4's `CalibrationGate` reflects real realized-outcome
history across process restarts, and fix `approve_trade_plan` to actually use that history
instead of a fresh empty tracker (which made approval permanently impossible regardless of how
many outcomes were recorded — a real bug found while implementing this task, not by design).

## Approach

- `calibration_entries` table in `SqliteStrategyStore`, mirroring the existing `bench_history`
  pattern exactly (`append_calibration_entry`/`get_calibration_entries`,
  `_row_to_calibration_entry`); included in `delete_artifact`'s cleanup.
- `CalibrationTracker.load_entries(entries)` (calibration.py): bulk-loads already-scored
  entries, trusting their stored scores rather than recomputing via `add_entry`.
- `record_realized_outcome(store, artifact_id, actual_return_pct, config=None)`
  (trade_plan_authoring.py): loads the artifact's frozen `TradePlan.forecast`, reuses
  `CalibrationTracker.add_entry`'s exact scoring (not a reimplementation), persists via
  `store.append_calibration_entry`.
- `load_calibration_tracker(store, artifact_id, config=None)`: rebuilds a tracker from
  persisted rows via `load_entries`.
- `approve_trade_plan`'s signature changed from `(store, artifact_id, tracker)` to
  `(store, artifact_id, config=None)` — it now always calls `load_calibration_tracker`
  internally rather than trusting a caller-supplied tracker, which is what let the original bug
  happen (the HTTP route built `CalibrationTracker(artifact_id)` fresh every call, silently
  empty forever). This is a deliberate breaking change to an internal-only function signature
  (not a public API) — existing Phase 4 tests were updated to seed entries via
  `record_realized_outcome`/`append_calibration_entry` instead of constructing a tracker
  directly.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_research/storage/strategy_store.py` | — | `calibration_entries` table, append/get, cleanup |
| `vinu_research/calibration.py` | — | `CalibrationTracker.load_entries` |
| `vinu_research/trade_plan_authoring.py` | — | `record_realized_outcome`, `load_calibration_tracker`; `approve_trade_plan` signature change |
| `vinu_research/server/routes_trade_plan.py` | — | Approve route now calls `approve_trade_plan(store, artifact_id)`; new `POST .../record-outcome` |
| `tests/test_trade_plan_authoring.py` | — | Updated `TestFreezeAndApprove` to the new persisted-entries API |

## Verification

- [x] Tests pass (`tests/test_calibration_persistence.py` 12 tests, updated `test_trade_plan_authoring.py`, `test_routes_trade_plan.py` +3 tests including a true end-to-end approve success via HTTP)
- [x] The bug is directly proven fixed: `test_succeeds_once_enough_realized_outcomes_recorded` posts 10 winning outcomes through the real HTTP endpoint and confirms `/approve` returns 200 — this would have failed against the pre-fix code (fresh empty tracker every call)
- [x] No runtime LLM call introduced outside `vinu-research`
