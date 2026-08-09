---
name: timer_timerxl-implementation
status: phase-1-done
purpose: the real record of implementing Timer's walk-forward backtest, fixing a real MIN_OBSERVATIONS/patch-size mismatch, and correcting a stale spec.yaml documentation bug.
---

# 27 — timer_timerxl — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/compute.py` | Edited | `MIN_OBSERVATIONS` raised 24→100 — not just cross-angle consistency: 100 > `PATCH_SIZE`(96) closes a real confusing-path bug the design doc identified (24-95 observations used to pass the floor check, then hit the real model's `n_patches<1` guard, and silently fall through to the fallback proxy). Extracted `_forecast()` — `compute()`'s external behavior unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/backtest.py` | New | `timer_timerxl_step` + `run_timer_timerxl_backtest` — multi-horizon (5-step), nested `predictions` dict, same shape as Chronos/Kronos. `hit` (direction on the real point forecast, primary metric) + `in_band` (CI-coverage on the post-hoc p10/p90 band, secondary/caveated metric) + RMSE/MAE components. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/naive_baseline.py` | New | RMSE/MAE-only naive baseline over the 5-step horizon. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/spec.yaml` | Edited | **Real documentation bug fixed**: title still said "(fallback proxy)" and purpose text still claimed no installable package exists — both stale since the 2026-08-06 models-wiring pass that actually wired real pretrained weights (same pass that fixed `kronos`'s spec.yaml, which this angle's file apparently missed). Corrected to match `kronos`'s treatment; outputs description updated to note the point forecast is the real model's native output and the p10/p90 band is post-hoc, not native uncertainty. |
| `vinu-initial-analysis/tests/test_timer_timerxl.py` | Edited | Replaced `test_fallback_proxy_for_sub_patch_context` (asserted the exact confusing-path behavior the `MIN_OBSERVATIONS` fix removes) with `test_below_floor_is_insufficient_data_not_a_silent_fallback` + a direct unit test on `_fallback_forecast()` confirming the proxy function itself still degrades gracefully on sub-patch data when reached through a different path (a real package/network failure, not an observation-count issue). |
| `vinu-initial-analysis/tests/test_timer_timerxl_backtest.py` | New | 6 tests. |

## How it was implemented

Group A, real pretrained weights (`thuml/timer-base-84m`, confirmed
actually loaded by `test_pretrained_backend_actually_loads_in_this_environment`,
which was already passing before this session's changes) — same
category as Chronos/Kronos, not the fallback-proxy angles. Multi-horizon
like Chronos/Kronos: `_forecast()` extracted from `compute()`'s inline
try/except, reused by both `compute()` and `backtest.py` unchanged.

The one real behavioral fix: raising `MIN_OBSERVATIONS` past
`PATCH_SIZE` doesn't just standardize the floor — it makes the real
model's own `n_patches < 1` fallback trigger inside `_forecast()`
literally unreachable through `compute()`'s public API now (100 // 96 =
1, always at least one patch once the floor is cleared). The trigger
itself wasn't removed — `_fallback_forecast()` is still exercised
directly by its own unit test, since the fallback path remains real and
reachable for genuine package/network failures regardless of how much
history is available.

The `spec.yaml` fix was flagged explicitly by the design doc as a
"recommended fix, not part of the backtest design itself" — applied here
since implementing this angle's backtest was the natural point to also
close it, matching the exact correction `kronos`'s own `spec.yaml`
already received in the same 2026-08-06 wiring pass this angle's file
had missed.

## Testing

7 pre-existing tests (1 replaced, 1 new direct-function test added) + 6
new backtest tests. Real-model integration tests (`test_real_pretrained_model_forecasts_expected_length`,
`test_pretrained_backend_actually_loads_in_this_environment`) already
existed and continued to pass unchanged — confirming the real weights
genuinely load in this environment, not just in principle. Backtest
tests use a real, several-step module-scoped fixture (not a single
minimal call) since Timer's real per-call cost, benchmarked directly, is
cheap once the model is warm-cached (~0.01s/call — much lighter than
Chronos-t5-large's ~14s/call, since Timer-base is 84M params with a
single deterministic forward pass, not 64-sample quantile sampling).

**Real-data validation (Phase 1: `1D`)**: the **full** real AAPL 1D
history (1025 real bars, 2022-2026 — not a small slice, since Timer's
low per-call cost made the full walk-forward genuinely affordable) → 921
real rows in 15.25s, confirmed `model_backend: "pretrained"` throughout
(the real weights, not the fallback proxy). Tags matched standalone
`tag_row`. Storage round-trip: zero mismatches. `unnest_predictions()`
correctly exploded 921 rows × 5 horizon steps into 4605 rows; grouped
hit-rate/coverage by horizon step matched a hand aggregation exactly.

**Real finding — the largest real sample of any angle checked this
session (921 real steps, not 21-25)**: directional accuracy holds
essentially flat at ~49-50% across all 5 horizon steps (coin-flip, no
real edge on this sample), CI-coverage on the post-hoc p10/p90 band
comes in at 71-75% (below the nominal 80% the band targets — a genuine
finding about the *bolted-on* spread's calibration, not the real
model's own uncertainty, which the design doc explicitly caveats this
metric can't speak to). RMSE/MAE both consistently worse than the naive
baseline at every horizon step (e.g. step 1: 4.125 vs. 3.288 RMSE) — the
same pattern seen across most trained/pretrained angles this session on
real AAPL daily data, now backed by a much larger, more statistically
meaningful real sample than any prior angle's check.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/27-timer_timerxl.md` — the decided design, including the spec.yaml staleness finding.
