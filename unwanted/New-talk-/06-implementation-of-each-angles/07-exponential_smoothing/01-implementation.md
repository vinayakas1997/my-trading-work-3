---
name: exponential_smoothing-implementation
status: phase-1-done
purpose: the real record of implementing exponential_smoothing's walk-forward backtest against the shared infrastructure.
---

# 07 — exponential_smoothing — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/exponential_smoothing/compute.py` | Edited | Renamed `_MIN_OBSERVATIONS`→`MIN_OBSERVATIONS` (public, matching every other angle's convention) and raised 10→100; extracted `_fit_and_forecast()` (`compute()` unchanged externally). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/exponential_smoothing/backtest.py` | New | `es_step` (direction-match hit, no CI exists for this model) + `run_es_backtest`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/exponential_smoothing/naive_baseline.py` | New | RMSE/MAE-only naive baseline, same pattern as ARIMA/Chronos. |
| `vinu-initial-analysis/tests/test_exponential_smoothing.py` | Edited | One existing test used `n=60`, now below the raised `MIN_OBSERVATIONS=100` — bumped to `n=100`. |
| `vinu-initial-analysis/tests/test_exponential_smoothing_backtest.py` | New | 6 tests. |

`spec.yaml` was already at the decided 6 timeframes (widened in an
earlier batch pass) — no change needed here.

## How it was implemented

Group A, structurally closest to DLinear: a bare point forecast with no
confidence interval (`statsmodels`' `ExponentialSmoothing` here doesn't
produce one), so the hit definition is direction-match, same as DLinear,
not CI-coverage like ARIMA/Chronos.

**Benchmarked real fit cost before writing the backtest**, same
discipline as every prior angle: a single fit costs **~0.014s** — about
37x cheaper than ARIMA's grid search — and `ExponentialSmoothingResults`
has no `.append()` incremental-refit method the way ARIMA's results
object does (confirmed directly: `hasattr(res, 'append') == False`). So
the design doc's own open "actual cadence to be set after benchmarking"
question has a real, simple answer: refit every single step, every
timeframe — no `N_1MIN`/`N_5MIN` cadence constants needed at all, unlike
ARIMA.

## Testing

6 new tests, synthetic data (fast — the cheap fit makes ARIMA-style
per-step loops entirely practical here). All pass together with the 5
pre-existing `test_exponential_smoothing.py` tests (one fixed — see
below).

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars → 25
rows in **0.91s total** (matches the benchmark). Tags matched standalone
`tag_row`. Storage round-trip and `query_slice` (by `day_of_week`) both
verified exactly against a hand pandas `groupby`.

**Real finding**: 48% directional accuracy (essentially coin-flip) and
naive again beat this model on RMSE (6.497 vs 6.672) — the same honest
pattern as ARIMA and Chronos on this identical real AAPL window. All
three point-forecast/statistical angles checked so far underperform "do
nothing" on this particular real 6-month window. Recorded as-is, not
explained away — a small, single-window sample, not a general claim about
any of these methods.

## Bugs found and fixed

**Bug 1 — a pre-existing test used `n=60`, now below the raised
`MIN_OBSERVATIONS=100`.** `test_forecast_close_to_recent_level_on_flat_series`
built a 60-bar synthetic series, fine under the old floor of 10, broken
under the decided 100. Caught by running the existing test file directly
before moving on, not by the full suite this time.
**Fix 1**: raised the test's synthetic series to `n=100`.

**Full `vinu-initial-analysis` suite**: 253 passed (up from 247
pre-this-angle — the 6 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `00-plan.md` — the pre-implementation plan, including the real
  fit-cost benchmark done before any backtest code was written.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/07-exponential_smoothing.md` — the decided design.
