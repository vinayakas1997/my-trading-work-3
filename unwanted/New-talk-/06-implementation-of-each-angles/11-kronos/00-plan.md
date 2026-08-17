---
name: kronos-implementation-plan
status: proposed
purpose: what will actually be done to implement Kronos's walk-forward backtest, and how it will be checked.
---

# 11 — kronos — Implementation Plan

## What the real code looks like today, and what I already benchmarked

`compute.py` already calls the real, pretrained `Kronos-base` (102.3M
params, vendored model code + real downloaded weights — already present
locally, confirmed) via `KronosPredictor(..., max_context=512)`, with a
genuine fallback MLP path if the real weights/network aren't available.
Forecasts full OHLC for 5 steps ahead. The code's own `MIN_OBSERVATIONS
= 30` + `CONTEXT_WINDOW = 32` only gate the **fallback** MLP path — the
real Kronos predictor's actual context requirement is the hardcoded
`max_context=512`, unrelated to those two constants. Per the decided
design ("512 (context window)... same treatment as Chronos"), the
walk-forward harness's `min_observations` needs to be 512, not 30+32=62.

**Benchmarked**: a real forecast call costs ~5.2s warm (~7.5s cold,
includes one-time model load, cached after). Same cost class as Chronos,
no incremental-refit path exists (a pretrained transformer, nothing to
partially update). Same conclusion as Chronos: a full-scale walk-forward
backtest is not the right Phase 1 shape here — use a small, real,
deliberately-limited slice instead.

## What I will actually do

1. Extract `_fit_and_forecast(bars) -> fields` (real predictor call +
   fallback path preserved) from `compute.py`'s `try/except` block —
   `compute()`'s external behavior stays unchanged.
2. `angles/kronos/backtest.py`: `kronos_step` — nested `predictions` dict
   keyed by horizon step (string keys, "1"-"5" — the exact same
   parquet-serialization fix Chronos needed, applying it from the start
   here instead of rediscovering it), each holding forecasted OHLC +
   `actual_close` + `predicted_direction`/`actual_direction`/`hit` +
   `close_sq_error` (for RMSE, computed at aggregation time — a raw
   per-row value isn't itself meaningful, same reasoning as GARCH's
   QLIKE). No weights store (pretrained, nothing trained).
3. `min_observations=512`, matching Chronos's fixed-context treatment,
   not a growing-window floor.
4. Naive baseline, same RMSE-per-horizon-step pattern as Chronos's.
5. Widen `spec.yaml` to the standard 6 (confirming current state first).
6. Unit tests — same constraint as Chronos: real model calls are
   expensive, so the real-model backtest tests run a small, fixed number
   of steps (module-scoped fixture, reused across assertions), not a
   per-test fresh backtest.

## How I will check it

Real Alpaca data, same policy as Chronos: `1D` isn't feasible (only 125
real daily AAPL bars available, far short of 512) — `1H` (1,011 real
bars) is the coarsest real, feasible timeframe. A deliberately small real
slice (~9 steps, matching Chronos's scale) for Phase 1, not a full
backtest. Checklist: bar sanity, row count, nested-predictions structure,
`unnest_predictions` + `query_slice` on real Kronos output, storage
round-trip, naive comparison, full suite.

## Open items

None — proceeding straight to implementation.
