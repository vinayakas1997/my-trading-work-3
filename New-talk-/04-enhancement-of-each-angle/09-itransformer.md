---
name: angle-09-itransformer
status: decided
purpose: discussion and enhancement proposal for the `itransformer` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/`.
---

# 09 — itransformer

**Title (from spec.yaml):** iTransformer Cross-Variate Attention Forecast

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/`
- Genuinely trained from scratch every call (real Adam optimizer,
  `MSELoss`, 50 epochs, `torch.manual_seed`) — same "no is-this-real
  caveat needed" status as DLinear, unlike angle 04.
- **Important caveat verified in the code's own docstring**: this is
  *not* the paper's true cross-asset design. The real iTransformer
  paper treats each **ticker/asset** as one attention token, so the
  model learns how different stocks relate to each other. This
  implementation only has **one ticker's data** available per call, so
  it instead treats each **channel** (`open, high, low, close, volume`)
  of that single ticker as a token, and runs attention across those 5
  channels instead. It's a real, working model — just not doing the
  cross-*asset* relationship learning the architecture was designed for.
  Same missing-multi-ticker-input blocker as angle 04's GCN piece — see
  [04-cross_attention_gcn_news_price_fusion.md](04-cross_attention_gcn_news_price_fusion.md).
- Source: Liu, Y., Hu, T., Zhang, H., Wu, H., Wang, S., Ma, L., Long, M.
  (2024), *"iTransformer: Inverted Transformers Are Effective for Time
  Series Forecasting,"* ICLR 2024, arXiv:2310.06625
  (https://arxiv.org/abs/2310.06625). Official implementation:
  https://github.com/thuml/iTransformer — unlike angle 04's paper, a
  real reference implementation exists, though this codebase's version
  is its own from-scratch reimplementation, not a port of that repo.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

iTransformer looks at a stock's recent open/high/low/close/volume
together (not just the closing price alone), lets those five signals
"pay attention" to each other to notice patterns like "when volume
spikes, price tends to do X," and gets freshly retrained from scratch
every single time it runs, then forecasts the next value for each of the
five signals — the `close` one is what gets reported as the price
prediction.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Channels | `open, high, low, close, volume` (code default, kept as-is) | each channel is embedded as one attention "token" — this is the channel-as-token workaround described in §1, not true cross-asset attention |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_BARS = 90`), same consistency move as ARIMA/DLinear/exponential_smoothing |
| Lookback window | 32 candles (code default `LOOKBACK = 32`, kept as-is) | how much history each channel-token's embedding sees |
| Model size | `D_MODEL = 16`, `NHEAD = 2`, `NUM_LAYERS = 1` (code defaults, kept as-is) | small transformer — tiny compared to Chronos's 710M params, but a real multi-head attention + encoder stack, unlike DLinear's pure linear layers |
| Training epochs | 50 (code default, kept as-is) | real Adam gradient-descent training happens every call |
| Random seed | fixed at 42 for the whole backtest | same reproducibility rationale as DLinear — isolates data-driven differences from init noise |
| Forecast horizon | 1 step ahead | matches ARIMA/DLinear, for comparability |
| Hit definition | directional accuracy — predicted `close` direction matches actual next-candle direction | no confidence interval in this model's output (point forecast only), same fix already used for DLinear/exponential_smoothing |
| Diagnostic fields stored | forecasted value for **all 5 channels** (`open, high, low, close, volume`), not just `close`; plus `train_loss` | the model already computes a forecast per channel internally — only reporting `close` and discarding the rest would throw away real, free output; keeping all 5 lets us later check e.g. whether the volume forecast is itself informative, or whether high/low forecasts bracket the actual range well |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as ARIMA/DLinear — a fresh model is trained at every single step |
| Weight storage | every walk-forward step's trained weights saved via `weights_ref`, none skipped/sampled | same artifact-store pattern as DLinear (`05-dlinear.md` §5) — model is small enough that per-step weight files stay cheap |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as ARIMA/DLinear |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as ARIMA/DLinear |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles — **single-ticker only**, see §1 caveat |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | open/unbenchmarked | real multi-head attention + encoder stack + 50 training epochs per call — more expensive than DLinear's <1,000-param linear model, though still far smaller than Chronos's 710M-parameter forward pass; whether a full 1min/5min walk-forward backtest is feasible without a refit-cadence compromise (like ARIMA/exponential_smoothing use) is not yet measured, same honesty caveat applied throughout this whole set of angles |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
lookback: 32
train_loss: 0.0091
forecast_open: 141.90
forecast_high: 143.10
forecast_low: 141.20
forecast_close: 142.55
forecast_volume: 58200000
actual_close: 142.80
predicted_direction: up
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
NY-MARKETHOURS-1330-2000-1D = 59.4% directional accuracy (n=912 forecasts), naive baseline = 51.2%
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as DLinear — one row per
  walk-forward step, tagged, plus all 5 per-channel forecast fields and
  a `weights_ref` pointer (same artifact-store pattern as DLinear's
  §5, reused as-is rather than redesigned).
- **Layer 2 — precomputed common keys**: same as ARIMA/DLinear — session
  + subsession + timeframe combinations precomputed with `n`.
- **Layer 3 — on-demand query service**: same shared service as the
  other angles.
- **Weights artifact store**: reuses DLinear's exact convention —
  `{symbol}_{timeframe}_{candle_ts}.pt`, referenced via `weights_ref`,
  not inlined into the row.

No new storage architecture needed — this is a direct reuse of DLinear's
3-layer design plus weights-artifact addition.

## 6) What we will achieve / how to use it

- A real, backtested directional-accuracy number per timeframe/session/
  day for iTransformer, directly comparable against ARIMA, DLinear, and
  exponential_smoothing since all share the same date range, symbols,
  and tagging.
- Visibility into all 5 channels' forecasts, not just `close` — e.g.
  whether the model's volume forecast tends to be informative, or
  whether its high/low forecasts meaningfully bracket the actual range,
  which the current code throws away by only reporting `close`.
- Since every model is retrained fresh per step with weights kept (same
  as DLinear), the ability to go back and inspect exactly what a specific
  historical model looked like.
- A honest baseline for how much this angle's attention-across-channels
  approach actually earns over the naive random-walk and over the much
  simpler DLinear, given both are trained-from-scratch-per-call models on
  the same data.
- Clear documentation (§1) of what this angle is *not* yet doing —
  cross-asset attention — so that if/when a multi-ticker mechanism gets
  built in the future (deferred, alongside angle 04's GCN, per the
  2026-08-07 discussion), it's understood this angle is the other
  natural consumer of it.

## 7) Deeper rationale

**Why directional accuracy instead of CI-coverage:** identical reasoning
to DLinear/exponential_smoothing — iTransformer's code outputs a single
point forecast per channel, no confidence interval anywhere in its
output, so directional accuracy is the natural, non-invented hit
definition rather than fabricating a threshold.

**Why store all 5 channel forecasts instead of just `close`:** the model
already computes a forecast for every channel as part of its normal
forward pass — `open`, `high`, `low`, and `volume` come at zero extra
compute cost, exactly like DLinear's `alpha`/`beta` diagnostics or
GARCH's `omega`/`persistence`. Discarding them and keeping only `close`
would throw away real model output for no reason — the same principle
already applied to every other angle with free diagnostic fields.

**Why N=100 instead of the code's current 90:** small bump for
consistency with the rest of the set (ARIMA 30→100, DLinear 80→100,
exponential_smoothing 10→100) — 90 was already close, so this is a minor
adjustment, not a meaningful redesign.

**Why weight storage reuses DLinear's exact pattern instead of a new
design:** both angles train a fresh, small model from scratch on every
walk-forward step — the same rationale for keeping every step's weights
(cheap storage, full reproducibility of any historical prediction)
applies identically here, so there's no reason to invent a second
convention.

**Why compute cost is flagged open here but not for DLinear:**
iTransformer runs real multi-head self-attention plus an encoder layer,
not a pure linear pass — meaningfully more expensive per training step
than DLinear's under-1,000-parameter model, even though its overall
parameter count (`D_MODEL=16`, single layer) is still small compared to
Chronos. Whether that's still cheap enough for a full 1min/5min
walk-forward run across ~440,000 candles is unmeasured, so the same
refit-cadence safety net used for ARIMA/exponential_smoothing may end up
being needed here too — but that's a decision to make after real
benchmarking, not now.

**The core open caveat — not true cross-asset attention:** the paper's
actual contribution is learning relationships *between different
tickers* (e.g. how AAPL and MSFT move together), by giving each ticker
its own attention token. This implementation, constrained by the
single-ticker `compute()` interface, repurposes the same attention
mechanism across one ticker's 5 data channels instead — a real,
functioning model, but answering a different question ("how do this
stock's own open/high/low/close/volume relate to each other") than the
one the architecture was designed to answer. Building the true
cross-asset version requires the same missing piece as angle 04's GCN —
multi-ticker input — and is deferred to future work rather than decided
now, per the 2026-08-07 discussion.
