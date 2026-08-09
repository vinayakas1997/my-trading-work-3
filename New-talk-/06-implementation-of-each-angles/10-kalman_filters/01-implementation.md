---
name: kalman_filters-implementation
status: phase-1-done
purpose: the real record of implementing kalman_filters' walk-forward backtest against the shared infrastructure.
---

# 10 — kalman_filters — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/kalman_filters/compute.py` | Edited | `MIN_OBSERVATIONS` (renamed public, raised 20→100). Split into `_fit()` + `_filtered_fields()` (causal only) + `_smoothed_fields()` (non-causal, kept structurally separate) + `compute()` (unchanged external behavior). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/kalman_filters/backtest.py` | New | `kalman_step` (filtered-state-only, direction hit) + `run_kalman_backtest` + `run_smoothed_diagnostic` (whole-history-only, separate function). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/kalman_filters/naive_baseline.py` | New | **Persistence**-based naive baseline, not the RMSE/MAE pattern — see "The naive-baseline decision" below. |
| `vinu-initial-analysis/tests/test_kalman_filters.py` | Edited | One test used `n=80`, below the raised floor — bumped to `n=100`. |
| `vinu-initial-analysis/tests/test_kalman_filters_backtest.py` | New | 7 tests. |

`spec.yaml` was already at the decided 6 timeframes.

## How it was implemented

Not a forecaster — `filtered_trend`'s sign is repurposed as a directional
signal, per the decided design. The one rule this whole implementation is
built around: **`smoothed_state` (a two-pass, whole-series estimate) must
never be used inside the walk-forward step** — the design doc calls using
it mid-backtest "a correctness bug, not a style choice," since it would
leak future information into what's supposed to be a causal prediction.
So `_filtered_fields()`/`_smoothed_fields()` are two separate functions,
`kalman_step` only ever calls the first, and `run_smoothed_diagnostic()`
is its own function producing one whole-history row per symbol/timeframe
— structurally impossible to accidentally wire into the backtest.

## The naive-baseline decision (worth naming — genuinely different from every prior angle)

This angle has no price forecast at all — `filtered_level` is a *state
estimate*, not "next price" — so there's no `forecast_price` to compute
RMSE/MAE against the way ARIMA/DLinear/Chronos/exponential_smoothing/
iTransformer's naive baselines do. The decided design's own worked
example illustrates a *directional-accuracy* naive baseline ("~51.2%"),
not an error metric. A "predict flat" naive model (the pattern used for
every prior direction-hit angle) would be degenerate here for the exact
same reason it was dropped there — real markets essentially never close
exactly flat, so it would score near 0%, not ~51%. **Decided**: this
angle's naive baseline is **persistence** — predict the next move
continues the same direction as the most recently realized move — the
standard, non-degenerate directional baseline that actually produces a
real ~50%-ish hit rate, matching the design doc's own illustrative
number rather than an invented one.

## Testing

7 new tests + 5 pre-existing (one fixed for the raised floor). Directly
tests the correctness-critical property: `run_kalman_backtest`'s output
never contains `smoothed_level`/`smoothed_trend` columns at all — a
structural guarantee, not just a code-review claim.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars → 25
rows in 1.33s. Tags matched standalone `tag_row`. Smoothed fields
confirmed absent from backtest rows on real data too (not just synthetic
tests). Storage round-trip and `query_slice` verified exactly against a
hand pandas `groupby`.

**Real finding — the first angle so far to actually beat naive on this
window**: 60% directional accuracy vs. the persistence baseline's 52%.
Every prior Group A angle (ARIMA, Chronos, exponential_smoothing,
iTransformer) lost to its naive comparison on this same real AAPL window;
this is the first one that didn't. Recorded plainly — one small (25-step,
one-symbol) real sample, not proof the filter is genuinely predictive,
but a real, positive result worth noting rather than downplaying just
because it breaks the pattern of the prior angles.

**Full `vinu-initial-analysis` suite**: 272 passed (up from 265
pre-this-angle — the 7 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `00-plan.md` — the pre-implementation plan, including the naive-baseline decision made before any code was written.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/10-kalman_filters.md` — the decided design.
