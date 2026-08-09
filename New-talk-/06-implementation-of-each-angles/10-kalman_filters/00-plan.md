---
name: kalman_filters-implementation-plan
status: proposed
purpose: what will actually be done to implement kalman_filters' walk-forward backtest, and how it will be checked.
---

# 10 — kalman_filters — Implementation Plan

## What the real code looks like today, and what I already benchmarked

`compute.py` already fits `statsmodels.tsa.statespace.structural.UnobservedComponents`
(local-linear-trend, a real 2-state Kalman filter/smoother) and reports
both `filtered_*` (causal) and `smoothed_*` (whole-series, non-causal)
state — matches the decided design closely already. `_MIN_OBSERVATIONS`
needs raising 20→100.

**Benchmarked**: a single fit costs ~0.026s — cheap, same class as GARCH,
no cadence trick needed, refit every step.

## The one correctness rule this angle is built around

`smoothed_state` uses the *entire* series (a backward pass), so using it
inside any walk-forward step would leak future information — the design
doc calls this "a correctness bug, not a style choice." So:
- **`backtest.py`'s step function only ever touches `filtered_state`**
  (causal, online) — never `res.smoothed_state`.
- **Smoothed state becomes its own separate, whole-history-only
  function**, `run_smoothed_diagnostic()`, computed once per symbol/
  timeframe over the full available range — same "stored separately"
  pattern as `backtesting_44_metrics`'s whole-history metrics.

## The naive-baseline decision (worth naming — not the same pattern as ARIMA/DLinear)

This angle has no natural price forecast at all — `filtered_level` is a
*state estimate*, not "next price," so there's no `forecast_price` to
compute RMSE/MAE against the way ARIMA/DLinear/iTransformer's naive
baselines do. The decided design's own worked example (§4) illustrates
`"naive baseline = 51.2%"` — a *directional-accuracy* percentage, not an
error metric — confirming this angle's comparison is direction-only.

But a "predict flat" naive baseline (the DLinear/iTransformer pattern)
would be degenerate here for the same reason it was dropped there — real
markets essentially never close exactly flat, so a flat-always guess
would score near 0%, not the ~51% the design doc's own example shows.
**Decided here**: the naive baseline for this angle specifically is
**persistence** — "the next move continues the same direction as the
most recently realized move" — the standard, non-degenerate directional
baseline, and the one that actually produces a real ~50%-ish hit rate
matching the design doc's own illustrative number, not an invented
threshold.

## What I will actually do

1. Extract `_fit(close) -> res` + `_filtered_fields(res)` from
   `compute.py` (external behavior unchanged), raise the floor to 100.
2. `angles/kalman_filters/backtest.py`: `kalman_step` (filtered-state-only,
   direction-match hit) + `run_kalman_backtest`. No weights store.
3. `run_smoothed_diagnostic()` — one row per symbol/timeframe, whole
   history, `smoothed_level`/`smoothed_trend` only.
4. `naive_baseline.py` — persistence-direction baseline, as decided above.
5. Widen `spec.yaml` to the standard 6 (confirming current state first).
6. Unit tests, synthetic data.

## How I will check it

Real Alpaca data, Phase 1 = `1D`, reusing already-fetched real AAPL data.
Checklist: bar sanity, row count, tags, filtered-vs-smoothed separation
actually verified (not just asserted), storage/query round-trip, naive
(persistence) comparison, full suite.

## Open items

None — proceeding straight to implementation.
