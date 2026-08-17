---
name: angle-08-garch
status: decided
purpose: discussion and enhancement proposal for the `garch` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/garch/`.
---

# 08 — garch

**Title (from spec.yaml):** GARCH Volatility Forecast

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/garch/`
- Not a price forecaster — forecasts **volatility** (magnitude of the
  next move), a different kind of target than ARIMA/DLinear/Chronos/
  exponential smoothing.
- Reuses the exact same `garch_volatility` function that `shock_personality`
  already uses internally (`vinu_tools.compute.risk.volatility.garch_volatility`)
  — this angle exposes that fit as its own first-class result rather than
  duplicating the math. Confirms `vinu-tools` is genuinely used as a
  shared library by `vinu-initial-analysis`, not just a separate,
  unrelated component.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

GARCH predicts how "jumpy" a stock's price is likely to be in the next
period — not which direction it'll move, just how big the moves are
likely to be — based on how jumpy it's been recently, since big price
swings tend to cluster together and gradually settle down rather than
appearing randomly.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Method | GARCH(1,1) | classical, foundational volatility model |
| Source | Bollerslev, T. (1986), *"Generalized Autoregressive Conditional Heteroskedasticity,"* Journal of Econometrics, 31(3), 307–327 | one of the most cited papers in econometrics; standard tool in risk management |
| Min observations (N) | 100 returns | raised from the code's current floor (20) — same consistency move as the other classical-method angles |
| Forecast horizon | 1 step ahead | matches the other angles |
| Realized volatility proxy | the actual next-period return, squared | the real-world value the forecast gets checked against — standard practice in volatility-forecast evaluation |
| Primary evaluation metric | QLIKE (and/or MSE) between forecasted variance and realized variance, per time-slice | continuous error metric, not a binary hit/miss — a magnitude forecast needs a magnitude-aware evaluation, not a threshold we'd have to invent |
| Secondary evaluation metric | directional accuracy on volatility — did GARCH correctly call "volatility rising" vs. "falling" relative to the recent period | supplementary, easier-to-read number alongside the primary continuous metric |
| Diagnostic fields stored | `alpha`, `beta`, `omega`, `persistence` (alpha+beta) | already real code output — `persistence` close to 1 means volatility spikes tend to linger a long time before settling |
| Backtest method | walk-forward (rolling refit + forecast + check, slide forward, repeat) | same method as ARIMA |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as ARIMA |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
alpha: 0.09
beta: 0.88
omega: 0.000002
persistence: 0.97
forecasted_variance: 0.00031
forecasted_volatility: 0.0176
actual_next_return: 0.0142
realized_variance: 0.000202   # actual_next_return squared
qlike_error: 0.31
forecasted_vol_direction: rising
actual_vol_direction: rising
vol_direction_hit: true
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
NY-MARKETHOURS-1330-2000-1D = QLIKE 0.28 (avg), vol-direction accuracy 64.1% (n=912 forecasts)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as the other angles — one
  row per walk-forward step, tagged, plus the diagnostic fields
  (`alpha`, `beta`, `omega`, `persistence`) and both evaluation metrics
  (continuous QLIKE/MSE error, plus the directional hit flag).
- **Layer 2 — precomputed common keys**: session + subsession +
  timeframe combinations precomputed with `n` — for this angle, the
  precomputed value is an **average** continuous error (not a
  percentage), alongside the directional accuracy percentage.
- **Layer 3 — on-demand query service**: same shared service as ARIMA.

Reuses the same 3-layer architecture as every other angle; the only
difference is Layer 2's precomputed metric is an averaged continuous
error value for the primary metric, not a hit-rate percentage, since
volatility forecasting is being evaluated as a magnitude problem, not a
binary one.

## 6) What we will achieve / how to use it

- A real, backtested answer to "how good is GARCH's volatility forecast,
  and where/when is it most accurate" — using the same rigorous,
  established evaluation approach (QLIKE) that real volatility-forecasting
  research uses, not an invented threshold.
- A risk-sizing signal: since GARCH's real-world use is estimating how
  much risk to expect next, not predicting direction, this backtest tells
  us how much to actually trust that risk estimate, broken down by
  session/timeframe.
- Confirms whether `vinu-tools`'s shared `garch_volatility` function
  (already used internally by `shock_personality`) is itself reliable —
  since this angle's backtest is effectively also validating that shared
  function.

## 7) Deeper rationale

**Why a continuous error metric instead of a binary hit/miss:**
volatility is a magnitude, not a direction — a forecast off by 5% and one
off by 200% are very different outcomes, but a binary hit/miss framing
would count both as simply "miss," discarding almost all the useful
information. QLIKE is the metric built specifically for this purpose in
real volatility-forecasting research, so using it is following
established practice, not inventing a new evaluation scheme (the same
principle already applied when we rejected an arbitrary ±5% band for
ARIMA in favor of using the model's own confidence interval).

**Why also report directional accuracy on volatility as a secondary
metric:** a raw QLIKE/MSE number isn't intuitive to read at a glance the
way a percentage is. Directional accuracy on volatility ("did it
correctly call rising vs. falling") gives a quick, readable sanity check
alongside the more rigorous primary metric, without replacing it.

**Why realized variance is approximated as the squared next-period
return:** with only one future observation to check against at each
walk-forward step, the actual squared return is the standard real-world
proxy for realized variance used in the literature — not a choice unique
to this design.

**Why N=100 instead of the code's current 20:** same reasoning applied
throughout this whole set of angles — a GARCH fit needs enough
observations to stabilize its parameter estimates, and 20 is far too thin
a floor for that, especially given the model already needs to estimate
three parameters (`alpha`, `beta`, `omega`).

**Open/unresolved:** compute cost across 1min/5min timeframes hasn't been
benchmarked — GARCH(1,1) fits are generally fast (a small numerical
optimization, not a grid search or neural network), so this is expected
to be cheap, but same as ARIMA/Chronos/exponential smoothing, this is an
expectation, not a measured fact.
