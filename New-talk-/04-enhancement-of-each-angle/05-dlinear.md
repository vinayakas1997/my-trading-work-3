---
name: angle-05-dlinear
status: decided
purpose: discussion and enhancement proposal for the `dlinear` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/`.
---

# 05 — dlinear

**Title (from spec.yaml):** DLinear Decomposition Linear Forecast

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/`
- Unlike angle 04, this is a genuinely working, genuinely trained model —
  no "is this real" caveat needed here.
- Source: DLinear comes from *"Are Transformers Effective for Time Series
  Forecasting?"* (Zeng, Chen, Zhang, Xu — AAAI 2023, arXiv:2205.13504
  https://arxiv.org/abs/2205.13504) — this paper showed a simple linear
  trend/seasonal decomposition model beats many transformer-based
  forecasters on real benchmarks.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

DLinear is a tiny model that gets freshly trained from scratch, on the
spot, every single time it runs — it splits recent prices into a smooth
"trend" and a leftover "wiggle," learns a simple pattern in each, and
adds them together to guess the next price, then says whether it thinks
price is going up, down, or staying flat.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_BARS = 80`), same consistency move as ARIMA's 30→100 |
| Lookback window | 30 candles (code default, kept as-is) | how much history each individual training example sees |
| Training epochs | 60 (code default, kept as-is) | real Adam gradient-descent training happens every call — cheap since the model is under 1,000 parameters |
| Random seed | fixed at 42 for the whole backtest | ensures every walk-forward step is reproducible; not varied per-step |
| Forecast horizon | 1 step ahead | matches ARIMA, for comparability |
| Hit definition | directional accuracy — predicted direction (up/down/flat) matches the actual next-candle direction | unlike ARIMA/Chronos, this model outputs a point forecast + threshold, not a confidence interval, so there's no CI to check coverage against — direction match is the natural, code-grounded hit definition here (the code's own docstring calls out "the reported ~50% directional-accuracy figure") |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as ARIMA — a fresh model is trained at every single step, not reused |
| Weight storage | every walk-forward step's trained weights are saved, none skipped/sampled | each model is <1,000 params, so each saved file is only a few KB — feasible to keep all of them, even across ~440,000 1-minute steps |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | same 6 as ARIMA |
| Date range | 2022-01-01 → 2026-Q2 | same as ARIMA |
| Data source | Alpaca | same as ARIMA |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as ARIMA |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as ARIMA |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | not expected to be a concern | model is tiny (<1,000 params, 60 epochs on ~50 windows) — sub-second fit even on CPU, unlike ARIMA's grid search or Chronos's transformer forward pass, so no refit-cadence workaround is expected to be needed even at 1min/5min |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
n_train_windows: 50
lookback: 30
train_loss: 0.0142
forecast_price: 142.55
forecast_return: 0.00175
direction: up
actual_close: 142.80
actual_direction: up
hit: true
weights_ref: AAPL_1D_2024-05-15T13-30-00Z.pt
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
NY-MARKETHOURS-1330-2000-1D = 61.2% directional accuracy (n=912 forecasts)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as ARIMA — one row per
  walk-forward step, fully tagged, plus a `weights_ref` pointer field
  (new addition, specific to trained-from-scratch angles like this one).
- **Layer 2 — precomputed common keys**: same as ARIMA — session +
  subsession + timeframe combinations precomputed with `n`.
- **Layer 3 — on-demand query service**: same shared service as ARIMA.
- **New: weights artifact store**: every trained model's weights are
  saved as a small separate file, named/keyed by
  `{symbol}_{timeframe}_{candle_ts}.pt`, referenced from the row via
  `weights_ref` rather than inlined into the tagged row itself. Keeps the
  raw-row table small and query-friendly while still making every
  individual trained model fully recoverable later (e.g. to reproduce a
  specific forecast, or study how the trend/seasonal weights drifted over
  time for a ticker).

This reuses the same 3-layer tagging architecture as ARIMA, with one
addition (the weights artifact store) that other trained-from-scratch
angles could reuse the same way, if they come up later.

## 6) What we will achieve / how to use it

- A real, backtested directional-accuracy number per timeframe/session/day
  — replacing the code's own vague "~50% directional-accuracy figure"
  comment with an actual measured value.
- Since every model is retrained fresh per step and every set of weights
  is kept, this is also the first angle where we can go back and inspect
  *how* the model reached a specific prediction, not just what it
  predicted — useful for debugging bad stretches or understanding drift.
- A genuine baseline comparison (vs. naive random-walk) to check whether
  this tiny linear model earns its keep, consistent with how "beats
  naive" is being checked for every angle.
- Reuses the same shared tagging/storage infrastructure as ARIMA and
  Chronos, so this backtest doesn't add new machinery beyond the one new
  weights-artifact piece.

## 7) Deeper rationale

**Why directional accuracy instead of CI-coverage:** DLinear's code
outputs a single point forecast and a thresholded direction — there is no
confidence interval anywhere in its output, unlike ARIMA (95% CI) or
Chronos (p10/p90 band). Forcing a CI-based hit definition onto a model
that doesn't produce one would mean inventing a threshold, which is
exactly what was rejected for ARIMA in favor of using the model's own
output. Directional accuracy is the metric this model's own code already
gestures at, so it's the natural, non-invented choice here.

**Why store every walk-forward step's weights instead of sampling:** the
model is tiny enough (under 1,000 parameters) that the storage cost of
keeping all of them is negligible compared to the value of being able to
reproduce or inspect any specific historical prediction later. Sampling
would save some disk space but lose the ability to say "show me exactly
what this model looked like right before it made this specific
prediction" for any arbitrary point in history.

**Why compute cost isn't flagged as an open caveat here, unlike ARIMA and
Chronos:** both of those have real, unresolved uncertainty about whether
a full 1-minute walk-forward backtest is computationally feasible without
some kind of refit-cadence compromise. DLinear's training cost per step
(60 epochs on ~50 tiny windows, well under 1,000 parameters) is orders of
magnitude cheaper than a 17-model ARIMA grid search or a 710M-parameter
Chronos forward pass, so this isn't expected to need the same kind of
compromise — though, same as the others, this is still an expectation,
not yet a measured fact.

**Why a fixed seed across the whole backtest instead of varying it:**
keeps every result reproducible and comparable across timeframes/tickers
— varying the seed per step would make it impossible to tell whether a
difference in results came from the data or from random initialization
noise.
