---
name: garch-implementation-plan
status: proposed
purpose: what will actually be done to implement garch's walk-forward backtest, and how it will be checked.
---

# 08 — garch — Implementation Plan

## What the real code looks like today, and what I already benchmarked

`compute.py` already calls the real, shared `vinu_tools.compute.risk.volatility.garch_volatility`
(the same function `shock_personality` uses internally) and reports
`alpha`/`beta`/`omega`/`persistence` plus a one-step-ahead volatility
forecast — very close to the decided design already. `n < 20` floor needs
raising to 100.

**Benchmarked**: a single fit on 100 real-shaped returns takes **~0.027s**
— cheap, same category as exponential_smoothing, no `.append()`/
incremental-refit concept exists for this custom ML-estimate function
either. Refit every step, every timeframe, no cadence trick needed.

## What this angle is actually forecasting (not price)

Not a price/direction forecaster — forecasts **volatility** (magnitude of
the next move). Evaluated with QLIKE (`realized_var/forecast_var -
ln(realized_var/forecast_var) - 1`, the standard metric in volatility-
forecasting research, per the decided design), not a hit/miss — a
continuous error, plus a secondary directional accuracy on volatility
itself ("did it correctly call rising vs. falling").

## What I will actually do

1. Extract `_fit_and_forecast(returns, time_format) -> (fields, ...)` from
   `compute.py` (unchanged external behavior), raise the floor to 100.
2. `angles/garch/backtest.py`: `garch_step` computes QLIKE against the
   actual next-period squared return (the realized-variance proxy the
   design doc specifies), plus `vol_direction_hit` (secondary metric:
   did forecasted volatility direction — vs. the model's own last fitted
   value — match the actual realized-volatility direction). No weights
   store.
3. This angle has **no naive-baseline requirement** in the decided
   design (unlike ARIMA/Chronos/exponential_smoothing) — volatility
   clustering means "yesterday's realized vol" is itself already a
   reasonable proxy baseline, but the design doc doesn't ask for one, so
   none is added here (not silently inventing scope beyond what's decided).
4. Widen `spec.yaml` to the standard 6 (confirming current state first).
5. Unit tests, synthetic data, same style as exponential_smoothing's.

## How I will check it

Real Alpaca data, Phase 1 = `1D`, reusing the already-fetched real AAPL
data. Checklist: bar sanity, row count, tags, QLIKE computed correctly
against a hand-checked example, storage/query round-trip, full suite.

## Open items

None — proceeding straight to implementation.
