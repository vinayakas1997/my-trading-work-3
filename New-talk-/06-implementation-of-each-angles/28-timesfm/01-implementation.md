---
name: timesfm-implementation
status: phase-1-done
purpose: the real record of implementing TimesFM's walk-forward backtest — closing two confirmed gaps (discarded deciles, undersized context) and treating CI-coverage as a genuine primary metric for the first time in this project's pretrained-angle set.
---

# 28 — timesfm — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/compute.py` | Edited | **Gap #1 fix**: `MAX_CONTEXT` raised 256→1024, matching the model's own documented default operating configuration (was running at a quarter of its normal context). **Gap #2 fix**: all 9 real decile levels (q10-q90) now kept in a `decile_forecasts` dict, not just q10/q90 — 7 of 10 real model outputs were being computed and discarded. `MIN_OBSERVATIONS` raised 30→100. Extracted `_forecast()` — `compute()`'s external behavior unchanged in kind (still returns point + band), changed in shape (`p10_forecast`/`p90_forecast` → `decile_forecasts` with all 9 levels, a real, deliberate output-shape change per the decided design, not an accidental break). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/backtest.py` | New | `timesfm_step` + `run_timesfm_backtest` — multi-horizon (5-step), nested `predictions` dict with all 9 real deciles per step, `hit` (CI-coverage on [q10,q90], **primary metric** — unlike Kronos/timer_timerxl, this model's quantile head is genuinely trained, not bolted on, so coverage tests real model calibration), per-decile pinball loss (9 levels, richer than lag_llama's 5 or moirai's 2), RMSE/MAE on q50. Uses an **expanding** window (not Chronos's fixed-window pattern) since TimesFM's context is a quality preference, not a hard per-call requirement — grows toward `MAX_CONTEXT` as more history becomes available. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/naive_baseline.py` | New | RMSE/MAE-only naive baseline over the 5-step horizon. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/spec.yaml` | Edited | Outputs description updated to describe all 9 real deciles instead of a p10/p90 band (this angle's `spec.yaml`/docstring were already accurate on the pretrained-vs-fallback question, per the design doc — no staleness bug here, unlike `timer_timerxl`). |
| `vinu-initial-analysis/tests/test_timesfm.py` | Edited | `test_real_pretrained_checkpoint_forecasts_expected_length` updated for the new `decile_forecasts` shape, plus a real monotonicity check (q10≤q50≤q90) on the model's own `fix_quantile_crossing=True` guarantee. |
| `vinu-initial-analysis/tests/test_timesfm_backtest.py` | New | 5 tests. |

## How it was implemented

Group A, real pretrained weights (`google/timesfm-2.5-200m-pytorch`,
confirmed already-accurately documented per the design doc — unlike
`timer_timerxl`, no stale-spec bug here). The one genuinely distinctive
design decision in this angle: **CI-coverage is the primary metric**, not
a caveated secondary one like every other quantile-emitting angle this
session (lag_llama, moirai, timer_timerxl) — because TimesFM's quantile
head is verified (against the real model card) to be a real, trained
part of the model (`use_continuous_quantile_head=True`,
`fix_quantile_crossing=True`), not a statistical construction bolted on
after a point forecast. This is the first angle in the whole
trained/pretrained set where the quantile band genuinely tests model
calibration, not proxy math.

`_fallback_forecast()` was also extended to emit all 9 decile levels
(derived from the same Gaussian spread already used for p10/p90), so the
fallback path's output shape matches the real model's — even though the
fallback's deciles are a statistical construction, not genuine
model output, keeping the shape consistent avoids a second, divergent
schema depending on which backend actually ran.

## Testing

4 pre-existing tests (1 updated for the new decile-shaped output,
including a real monotonicity check) + 5 new backtest tests. Real-model
integration test already existed and continued to pass, confirming real
weights load in this environment. Backtest tests use a real,
several-step module-scoped fixture (Timer's real per-call cost,
benchmarked directly, is cheap once warm — ~0.15s/call).

**Real-data validation (Phase 1: `1D`)**: 300 real AAPL daily bars (the
most recent slice of the full real 2022-2026 history — a larger real
sample than most angles' 21-25-row checks, kept below the full 1025-bar
history purely for backtest runtime given the expanding-window,
up-to-1024-context cost per call) → 196 real rows in 33.6s, confirmed
`model_backend: "pretrained"` throughout. Tags matched standalone
`tag_row`. Storage round-trip: zero mismatches. `unnest_predictions()`
correctly exploded 196 rows × 5 horizon steps into 980 rows; grouped
coverage by horizon step matched a hand aggregation exactly.

**Real finding — genuinely well-calibrated coverage, a first for this
project's quantile-emitting angles**: CI-coverage decays smoothly from
88% (step 1) to 80% (step 5) — landing almost exactly on the model's own
nominal 80% band by the last horizon step, on a real 196-step sample.
This is meaningfully better-calibrated than lag_llama's 90%→71% or
moirai's 90%→33% decay on identical AAPL data (both angles ago in this
session) — consistent with the design doc's expectation that a genuinely
trained quantile head (verified against the model card) should calibrate
better than a post-hoc Gaussian band. RMSE/MAE track almost exactly with
the naive baseline at every step (e.g. step 1: 3.415 vs. 3.453 RMSE) —
TimesFM's point forecast doesn't clearly beat "assume no change" on this
real sample, but its probabilistic calibration is real and measurably
strong.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/28-timesfm.md` — the decided design, including both confirmed-gap fixes.
