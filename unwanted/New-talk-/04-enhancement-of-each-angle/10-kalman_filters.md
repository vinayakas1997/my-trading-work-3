---
name: angle-10-kalman_filters
status: decided
purpose: discussion and enhancement proposal for the `kalman_filters` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/kalman_filters/`.
---

# 10 — kalman_filters

**Title (from spec.yaml):** Kalman Filter State Estimation

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/kalman_filters/`
- Fundamentally different shape from every angle so far: this is **not a
  forecaster**. The code's own docstring and spec explicitly say so — it
  recursively estimates the *current* hidden "true" price level and trend
  from noisy observations (a classical predict-then-correct Kalman
  recursion, implemented via `statsmodels.UnobservedComponents` with
  `level="local linear trend"`), not a prediction of a future value.
  We're repurposing its `filtered_trend` sign as a directional signal so
  it can be backtested the same way as DLinear, matching the approach
  used when a model has no built-in forecast/CI to check against.
- Classical statistical fit (like ARIMA/exponential_smoothing/GARCH), not
  a trained neural net — no weight-artifact storage needed here, unlike
  DLinear/iTransformer.
- Source: Kalman, R.E. (1960), *"A New Approach to Linear Filtering and
  Prediction Problems,"* Journal of Basic Engineering, 82(1), 35-45 — the
  foundational paper this whole method is named after.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

This method assumes a stock's real, underlying price is smoother and
less noisy than what actually trades tick-to-tick, and continuously
re-estimates that smoothed-out "true" price and its current direction of
drift, updating its estimate one candle at a time as new data comes in.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Method | local-linear-trend structural time series model (2-state Kalman filter/smoother: level + trend), fit via `statsmodels.UnobservedComponents` | matches the real code exactly — a maximum-likelihood-fitted Kalman filter, not a hand-rolled recursion |
| Min observations (N) | 100 candles | raised from the code's current floor (`_MIN_OBSERVATIONS = 20`) — same consistency move as every other classical-fit angle |
| Forecast horizon | 1 step ahead | matches ARIMA/DLinear, for comparability — repurposed from a state-estimate into a directional signal, see below |
| Hit definition | directional accuracy — sign of `filtered_trend` at step T (up if positive, down if negative) compared against the actual next-candle direction | same fix as DLinear/exponential_smoothing: this model has no forecast or CI to check natively, so its own real output (the estimated trend direction) is repurposed as the testable signal, rather than inventing something new |
| Filtered vs. smoothed usage | **only `filtered_state`** (the causal, online estimate) is used inside the walk-forward backtest; `smoothed_state` (two-pass, uses the whole series) is reported as a separate, whole-history-only diagnostic, never used mid-backtest | smoothed state is computed using future observations relative to any given point — using it inside a walk-forward step would be look-ahead bias; same time-sliceable vs. whole-history-only split already used for angle 02's metrics |
| Diagnostic fields stored | `filtered_level`, `filtered_level_std`, `filtered_trend`, `filtered_trend_std` per row (all real code output, causal) | free from the fit, kept per step for the same reason ARIMA/GARCH/exponential_smoothing keep their diagnostic fields — enables later checking e.g. whether high uncertainty (`filtered_trend_std`) correlates with lower hit-rate |
| Whole-history-only fields | `smoothed_level`, `smoothed_trend` (final state only, from a single whole-series fit per symbol/timeframe) | kept as a separate one-per-symbol-per-timeframe diagnostic, not per walk-forward row, since it can't be computed causally at each step |
| Backtest method | walk-forward (rolling refit + estimate + check, slide forward, repeat) | same method as ARIMA/DLinear |
| Refit cadence | flexible per timeframe, named constants, same open-ended approach as ARIMA | actual cadence set after benchmarking real fit time |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as ARIMA/DLinear |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as ARIMA/DLinear |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | not expected to be a concern, but unbenchmarked | a 2-state Kalman filter fit is a small numerical optimization (similar cost class to GARCH(1,1)), not a grid search or neural network — expected cheap, but same honesty caveat as every other angle: expectation, not a measured fact |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
filtered_level: 142.31
filtered_level_std: 0.84
filtered_trend: 0.14
filtered_trend_std: 0.06
predicted_direction: up
actual_close: 142.80
actual_direction: up
hit: true
```

**After tagging** (per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)):

```
+ session: ny
+ subsession: markethours
+ day_of_week: Wednesday
+ week_of_month: 3
+ month: May
+ quarter: Q2
```

**After aggregation (queryable key):**

```
NY-MARKETHOURS-1330-2000-1D = 56.7% directional accuracy (n=912 forecasts), naive baseline = 51.2%
```

**Whole-history-only diagnostic (one per symbol/timeframe, not per row):**

```
symbol: AAPL
timeframe: 1D
smoothed_level: 143.02   # final state, two-pass fit over the entire date range
smoothed_trend: 0.11
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as ARIMA/DLinear — one row
  per walk-forward step, tagged, plus the causal diagnostic fields
  (`filtered_level`, `filtered_level_std`, `filtered_trend`,
  `filtered_trend_std`).
- **Layer 2 — precomputed common keys**: same as ARIMA — session +
  subsession + timeframe combinations precomputed with `n`.
- **Layer 3 — on-demand query service**: same shared service as ARIMA.
- **Whole-history-only diagnostic**: `smoothed_level`/`smoothed_trend`
  stored once per symbol/timeframe (not per walk-forward row), same
  pattern as angle 02's whole-history-only metrics — clearly separated
  from the per-row backtest data so it's never mistaken for a
  causally-valid, per-step value.

Reuses the same 3-layer architecture as every other angle; the only
addition is the whole-history-only smoothed-state diagnostic, kept
structurally separate from the causal backtest rows.

## 6) What we will achieve / how to use it

- A real, backtested directional-accuracy number per timeframe/session/
  day for the Kalman filter's trend-sign signal, directly comparable
  against ARIMA, DLinear, exponential_smoothing, and iTransformer, since
  all share the same date range, symbols, and tagging.
- A genuinely different kind of signal from the other angles — this one
  is explicitly a *denoised current-state estimate with uncertainty*,
  not a forecast — so its directional hit-rate tells us something
  different: whether "what does the underlying trend look like right
  now, once noise is filtered out" is itself a useful trading signal,
  independent from any model's ability to predict the future.
- The uncertainty fields (`filtered_trend_std`) give a natural
  confidence-weighting angle other trend-based methods don't have in the
  same form — e.g. checking whether hit-rate is higher when
  `filtered_trend_std` is low (the filter is confident) vs. high (noisy,
  uncertain estimate).
- A whole-history smoothed-state view (`smoothed_level`/`smoothed_trend`)
  as a separate, non-causal reference. Concrete use: it's a hindsight
  "ground truth" trend estimate we can compare the causal `filtered_*`
  values against, after the fact — e.g. plotting `filtered_trend` vs.
  `smoothed_trend` over the same date range reveals whether the live,
  causal filter systematically **lags** the true trend (common with
  online filters — it only knows the past, so it reacts late to turns)
  or is unusually **noisy** relative to what hindsight shows was really
  happening. That's a real diagnostic for how much to trust the causal
  signal, not something we could get from the filtered state alone.

## 7) Deeper rationale

**Why repurpose `filtered_trend`'s sign as a directional signal instead
of leaving this angle unbacktested (like angle 04):** unlike angle 04's
cross-attention model (untrained, genuinely non-functional as a
predictor), this Kalman filter is a fully real, working, maximum-
likelihood-fitted state estimator — it just wasn't originally framed as
a forecaster. Its trend estimate is a real, causal, per-step number that
naturally implies a directional bet ("locally trending up" vs. "locally
trending down"), so treating its sign as a testable signal is a
legitimate reuse of real model output, not an invented one — the same
reasoning already applied to DLinear and exponential_smoothing's
directional-accuracy hit definitions.

**Why filtered state only, never smoothed state, inside the backtest:**
`smoothed_state` in `statsmodels`' Kalman smoother implementation is
computed via a backward pass that incorporates the *entire* series,
including observations after any given timestep. Using it inside a
walk-forward loop at an intermediate step would silently leak future
information into a "prediction" that's supposed to be causal — a
correctness bug, not a style choice. Keeping it as a separate,
whole-history-only diagnostic (computed once, using the full available
range) preserves its genuine research value (e.g. "with hindsight, what
was the real underlying trend") without contaminating the live-tradeable
backtest.

**Why N=100 instead of the code's current 20:** same reasoning applied
throughout — 20 observations is too thin for a maximum-likelihood fit of
even a 2-state model (level + trend, each with its own noise variance)
to stabilize meaningfully.

**Open/unresolved:** compute cost across 1min/5min timeframes hasn't been
benchmarked — expected cheap (small numerical optimization, similar cost
class to GARCH(1,1)) but, consistent with the rest of this angle set,
this is an expectation, not yet a measured fact.
