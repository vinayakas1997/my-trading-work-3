# Task 3: Calibration Tracking

**Status:** DONE

## Purpose

Implement CalibrationTracker that extends the existing decay.py pattern to track forecast accuracy over time, and CalibrationGate — the fail-closed gate `approve_trade_plan` (Task 5) checks before promoting a plan to ACTIVE.

## Approach

- `CalibrationEntry`/`CalibrationResult` (models.py): forecast direction, actual return, Brier score, magnitude error.
- `CalibrationTracker`: in-memory sliding window of entries per `artifact_id`; entries are populated by Phase 6/7's realized-outcome feedback (out of scope here — see `plan.md` row 7). `evaluate()` delegates to `forecast_skill.compute_calibration`.
- `CalibrationGate`: `is_open()`/`check()` — fails closed both when `n_entries < min_window` and when the tracker's `compute_calibration` result doesn't clear the accuracy/Brier/magnitude thresholds.

## Bug found and fixed during implementation

`approve_trade_plan` originally constructed `CalibrationGate(tracker)` without a `min_window`,
so it silently used the gate's own default of 10 instead of the tracker's
`ForecastSkillConfig.min_calibration_window` — a tracker configured with a smaller window would
still be rejected by the gate. Fixed by passing `min_window=tracker.config.min_calibration_window`
explicitly in `trade_plan_authoring.approve_trade_plan`.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_research/calibration.py` | 1-100 | No change needed — file was already correct once `forecast_skill`'s imports were fixed |
| `vinu_research/trade_plan_authoring.py` | `approve_trade_plan` | Sync `CalibrationGate`'s `min_window` with the tracker's configured window (bug fix above) |

## Verification

- [x] Tests pass (`tests/test_calibration.py`, 7 tests)
