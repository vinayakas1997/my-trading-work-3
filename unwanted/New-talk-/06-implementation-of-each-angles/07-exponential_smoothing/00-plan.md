---
name: exponential_smoothing-implementation-plan
status: proposed
purpose: what will actually be done to implement exponential_smoothing's walk-forward backtest, and how it will be checked.
---

# 07 — exponential_smoothing — Implementation Plan

## What the real code looks like today, and what I already benchmarked

`compute.py` already fits `statsmodels.tsa.holtwinters.ExponentialSmoothing`
(Holt's linear trend, `trend="add"`, no seasonal) fresh each call and
reports `forecast`/`alpha`/`beta`/`level`/`trend`/`sse` — closely matches
the decided design already. `_MIN_OBSERVATIONS = 10` needs raising to
100.

**Benchmarked before writing any backtest code** (same discipline as
ARIMA/Chronos): a single fit on 100 real-shaped observations takes
**~0.014s** — about 37x cheaper than ARIMA's grid search — and
`ExponentialSmoothingResults` has **no `.append()`/incremental-refit
method** the way ARIMA's results object does, so there's no cheap
partial-update path even if I wanted one. Given the real cost is
negligible, the answer to the design doc's own open "actual cadence to be
set after benchmarking" question is simply: **refit every single step,
every timeframe** — no `N_1MIN`/`N_5MIN` cadence trick needed at all, a
real measured answer, not deferred again.

## What I will actually do

1. Extract `_fit_and_forecast(close) -> (fields, res)` from `compute.py`,
   same pattern as every prior angle — `compute()`'s external behavior
   unchanged. Raise `_MIN_OBSERVATIONS` 10→100.
2. `angles/exponential_smoothing/backtest.py`: `es_step` (direction-match
   hit, same as DLinear — this model has no CI/band, only a point
   forecast) + `run_es_backtest`, `refit_cadence=1` uniformly (per the
   benchmark above), fixed rolling `window=100`. No weights store.
3. Naive baseline, same RMSE/MAE-only pattern as ARIMA/Chronos.
4. Widen `spec.yaml` to the standard 6 (currently 1D-only, confirming
   before assuming).
5. Unit tests — synthetic data, same style as ARIMA's (cheap enough here
   to loop many steps, unlike Chronos).

## How I will check it

Real Alpaca data, Phase 1 = `1D` (same as ARIMA/backtesting_44_metrics —
already-fetched real AAPL data can be reused directly, no new fetch
needed). Full checklist: bar sanity, row count, tags, hit-definition
check, storage/query round-trip, naive comparison, full test suite.

## Open items

None — proceeding straight to implementation.
