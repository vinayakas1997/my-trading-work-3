---
name: angle-07-exponential_smoothing
status: decided
purpose: discussion and enhancement proposal for the `exponential_smoothing` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/exponential_smoothing/`.
---

# 07 — exponential_smoothing

**Title (from spec.yaml):** Exponential Smoothing Classical Baseline

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/exponential_smoothing/`
- Structurally close to ARIMA (real classical statistical method, fit
  fresh from scratch every call), but simpler math and no confidence
  interval — same design pattern as DLinear for the hit definition.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

This method tracks a price series as two smoothly-updating numbers — a
"level" (roughly, where the price is right now, smoothed out) and a
"trend" (roughly, how fast it's currently drifting up or down) — giving
more weight to recent prices than old ones, and adds the two together for
a one-step-ahead forecast.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Method | Holt's linear trend method (double exponential smoothing), level + trend, no seasonal component | matches the real code (`statsmodels.tsa.holtwinters.ExponentialSmoothing`, `trend="add"`, `seasonal=None`) — no seasonal term is correct since daily-bar equity data has no reliable fixed seasonal period |
| Source | Holt, C.C. (1957), *"Forecasting seasonals and trends by exponentially weighted averages"* (O.N.R. Memorandum No. 52, Carnegie Institute of Technology) | foundational classical forecasting method, predates ARIMA/Box-Jenkins |
| Min observations (N) | 100 candles | raised from the code's current floor (`_MIN_OBSERVATIONS = 10`) — same consistency move as ARIMA's 30→100, DLinear's 80→100 |
| Forecast horizon | 1 step ahead | matches ARIMA, for comparability |
| Hit definition | directional accuracy — predicted direction matches actual next-candle direction | no confidence interval in this model's output (only a point forecast), so CI-coverage doesn't apply — same fix already used for DLinear |
| Diagnostic fields stored | `alpha` (level smoothing), `beta` (trend smoothing), fitted `level`, fitted `trend`, `sse` (fit error) | all real `statsmodels` output, kept per row at no extra cost — enables checking things like "does the trend-smoothing parameter behave differently in volatile sessions," not just bare forecast+hit |
| Backtest method | walk-forward (rolling refit + forecast + check, slide forward, repeat) | same method as ARIMA |
| Refit cadence | flexible per timeframe, named constants (`N_1MIN`, `N_5MIN`, `N_15MIN`, `N_1H`, `N_4H`, `N_1D`) | refit every step for 1D/4H/1H; refit every N candles for 1min/5min — same open-ended approach as ARIMA, actual cadence to be set after benchmarking real fit time |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as ARIMA |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as ARIMA — checks Holt's method actually beats doing nothing |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
alpha: 0.82
beta: 0.11
level: 142.10
trend: 0.18
sse: 412.6
forecast: 142.28
actual_close: 142.80
predicted_direction: up
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
NY-MARKETHOURS-1330-2000-1D = 57.8% directional accuracy (n=912 forecasts), naive baseline = 51.2%
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as ARIMA/DLinear — one row
  per walk-forward step, tagged, plus the diagnostic fields (`alpha`,
  `beta`, `level`, `trend`, `sse`).
- **Layer 2 — precomputed common keys**: same as ARIMA — session +
  subsession + timeframe combinations precomputed with `n`.
- **Layer 3 — on-demand query service**: same shared service as ARIMA.

Reuses the exact same 3-layer architecture and metadata conventions
already defined for ARIMA/DLinear — no new storage design needed.

## 6) What we will achieve / how to use it

- A real, backtested directional-accuracy number per timeframe/session/
  day for Holt's method, comparable directly against ARIMA, DLinear, and
  the naive baseline — since all use the same date range, symbols, and
  tagging.
- Visibility into how the fitted smoothing parameters (`alpha`, `beta`)
  themselves behave across sessions/timeframes — e.g. whether the model
  leans more heavily on recent data (`alpha` closer to 1) during volatile
  periods, a diagnostic the raw forecast number alone wouldn't show.
- A cheap, classical reference point — since this is one of the simplest
  real methods in the whole set of angles, it's a useful sanity check for
  whether more complex methods (ARIMA, DLinear, Chronos) are actually
  earning their extra complexity.

## 7) Deeper rationale

**Why N=100 instead of the code's current 10:** the code's floor of 10
observations is far too low for a level+trend fit to stabilize
meaningfully — same reasoning as ARIMA's 30→100 change, applied here for
consistency across all angles rather than leaving each at its own
arbitrary original floor.

**Why directional accuracy instead of forcing a confidence interval:**
this model's output is a bare point forecast — `statsmodels`'
`ExponentialSmoothing` here doesn't produce a prediction interval the way
ARIMA's `get_forecast().conf_int()` does. Inventing a CI would mean
fabricating a threshold, which was already rejected for ARIMA in favor of
using the model's own real output — directional accuracy is what this
model actually gives us without invention, same reasoning as DLinear.

**Why store alpha/beta/level/trend/sse per row:** these come for free
from the fit (no extra compute), and keeping them enables later analysis
that the bare forecast+hit fields can't support — e.g. checking whether
the model's own confidence in trend vs. level shifts by session, or
whether high-SSE fits correlate with lower hit-rates.

**Why compute cost isn't expected to be a problem, but is still an open
caveat:** Holt's method is a single, simple optimization (no 17-model
grid search like ARIMA, no neural network forward pass like Chronos), so
it's expected to be cheap even across ~440,000 1-minute candles — but,
consistent with the honesty policy applied to ARIMA and Chronos, this is
an expectation, not a benchmark. The same flexible refit-cadence
constants (`N_1MIN`, `N_5MIN`, etc.) are kept as a safety net, with the
actual values to be set only after real measurement.
