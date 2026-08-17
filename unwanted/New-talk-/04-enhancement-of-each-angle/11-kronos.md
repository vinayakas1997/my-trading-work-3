---
name: angle-11-kronos
status: decided
purpose: discussion and enhancement proposal for the `kronos` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/kronos/`.
---

# 11 — kronos

**Title (from spec.yaml):** Kronos Financial K-Line Foundation Model

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/kronos/`
- Currently genuinely `pretrained` — real foundation-model weights
  (`NeoQuasar/Kronos-base`) are downloaded and loaded at run time, not a
  fallback. The code does have a `fallback_proxy` path (a tiny
  freshly-trained MLP, used only if the real weights/network are
  unavailable at runtime), but since weights are confirmed present and
  loaded, this backtest design does not need to account for
  fallback-proxy results mixing in — same call already made for Chronos.
- **Decided checkpoint: `Kronos-base` (102.3M params)** — matches the
  code's current default, kept as-is. Full size table (mini/small/base/
  large) with the trade-off written out explicitly in §7 before this was
  decided.
- Unlike Chronos, this model is purpose-built for financial K-lines
  specifically (pretrained on 12B real candle records from 45
  exchanges), rather than a general time-series foundation model adapted
  to finance.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

Kronos is a ready-made AI model, built once and pretrained specifically
on billions of real financial candles from dozens of exchanges (not
trained on our own data), that reads the recent candle history and
predicts the next 5 full candles (open, high, low, and close), not just
a closing price.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Context window | 512 candles | the code's own hardcoded `KronosPredictor(..., max_context=512)` — a fixed requirement, same treatment as Chronos's 512 ceiling, not a growing window like ARIMA's N=100 |
| Model checkpoint | `Kronos-base` (102.3M params) | matches the code's current default — see full size table in §7; the other real sizes were not silently hidden |
| Forecast horizon | 5 steps ahead, full OHLC per step | fixed output shape of this model (`HORIZON = 5` in code), same horizon length as Chronos, but Kronos forecasts the whole candle (open/high/low/close) at each step, not just close |
| Uncertainty band | none exposed | the model samples internally (`sample_count=3`, `T=0.8`, `top_p=0.9`) but the code only returns one point forecast per step — no quantile band the way Chronos exposes p10/p90 |
| Primary evaluation metric | directional accuracy on `close`, checked independently per horizon step (1 through 5) | same fix as DLinear/iTransformer: no CI/band exists in this model's actual output, so direction-of-close is the natural, non-invented per-step signal |
| Secondary evaluation metric | RMSE between forecasted `close` and actual `close`, per horizon step, aggregated per time-slice | directional accuracy alone hides *how close* a "wrong" call actually was — a miss by $0.05 and a miss by $5 both just count as "false." RMSE keeps that magnitude information, same reasoning already applied to GARCH's QLIKE addition (magnitude metric alongside a directional one) |
| Diagnostic fields stored | forecasted `open`, `high`, `low`, `close` per horizon step (all real model output, not just close), plus per-step squared error (`close_sq_error`) used to compute RMSE at aggregation time | same reasoning as iTransformer — the model already predicts full OHLC, discarding open/high/low would throw away free, real output; squared error stored per row so RMSE can be computed correctly (RMSE is a sqrt-of-mean, not meaningful as a single-row value) |
| Model backend | always `pretrained` | fallback_proxy path exists in code but out of scope here, real weights confirmed loaded |
| Backtest method | walk-forward (rolling predict + check + slide) | same method as ARIMA/Chronos |
| Storage shape | one row per walk-forward evaluation, nested `predictions` dict keyed by horizon step (1-5), each holding forecasted OHLC/actual-close/hit | same nested-dict pattern as Chronos §5, for the same reason (avoid repeating tags 5x per row) |
| Min observations (N) | 512 (context window) + enough history to run a full walk-forward backtest across the date range | same treatment as Chronos — the 512 context is a hard requirement per forecast call, not a tunable floor |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as ARIMA/Chronos |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as ARIMA/Chronos |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | open/unbenchmarked | 102M-param transformer forward pass with internal 3x sampling per call — meaningfully more expensive than DLinear/iTransformer, in a similar cost class to Chronos; not yet measured across the finer timeframes |

## 4) Example — what one result looks like

**One walk-forward evaluation (one row, nested predictions):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
session: ny
subsession: markethours
day_of_week: Wednesday
week_of_month: 3
month: May
quarter: Q2
model_backend: pretrained
checkpoint: Kronos-base
predictions: {
  1: {open: 142.1, high: 143.4, low: 141.6, close: 142.8, actual_close: 142.8, predicted_direction: up, actual_direction: up, hit: true, close_sq_error: 0.00},
  2: {open: 142.7, high: 144.0, low: 142.0, close: 143.3, actual_close: 143.1, predicted_direction: up, actual_direction: up, hit: true, close_sq_error: 0.04},
  3: {open: 143.2, high: 145.1, low: 142.5, close: 144.5, actual_close: 145.9, predicted_direction: up, actual_direction: up, hit: true, close_sq_error: 1.96},
  4: {open: 144.4, high: 145.9, low: 143.6, close: 144.9, actual_close: 144.0, predicted_direction: up, actual_direction: down, hit: false, close_sq_error: 0.81},
  5: {open: 144.7, high: 146.2, low: 143.0, close: 143.5, actual_close: 141.2, predicted_direction: down, actual_direction: down, hit: true, close_sq_error: 5.29}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 71% directional accuracy, RMSE 0.61 (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 54% directional accuracy, RMSE 2.14 (n=912)
```

(Same expected decay-by-horizon-step pattern as Chronos — both accuracy
dropping and RMSE growing with horizon are real, measurable findings, not
assumed in advance.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation,
  tags applied once per row (not per horizon step), predictions nested
  as a dict keyed 1-5 as shown in §4, each holding full OHLC + hit.
- **Layer 2 — precomputed common keys**: session + subsession +
  timeframe + horizon_step combinations precomputed after each run, each
  carrying `n`, directional accuracy, **and RMSE** (computed as
  `sqrt(mean(close_sq_error))` across all rows in that bucket — RMSE
  itself only makes sense as an aggregate, so it's always a Layer 2/3
  value, never a raw per-row field).
- **Layer 3 — on-demand query service**: same shared service as
  Chronos, unpacks the nested `predictions` dict to answer any custom
  key combination not already in Layer 2.

Reuses the exact same 3-layer architecture and nested-predictions
storage pattern already defined for Chronos — no new storage design
needed for this angle.

## 6) What we will achieve / how to use it

- A real, measured answer to "does Kronos's zero-shot forecast actually
  hold up on real price data," per timeframe and per how-far-ahead it's
  predicting — same question already being asked of Chronos, now
  answerable for a finance-specific foundation model instead of a
  general-purpose one.
- A direct comparison against Chronos's step-1/step-5 results, ARIMA,
  DLinear, and iTransformer — since all share the same date range,
  symbols, and tagging, this answers "does a model actually pretrained
  on financial candle data outperform a general time-series model, or a
  simple statistical/linear method, on our real data."
- Full OHLC forecast visibility per step (not just close) — enables
  checking whether Kronos's high/low forecasts meaningfully bracket the
  actual candle range, a genuinely different question than pure
  directional accuracy on close.
- Accuracy-decay-by-horizon-step visibility, same as Chronos — how far
  ahead this model can actually be trusted.

## 7) Deeper rationale

**Model checkpoint sizes — the full trade-off, not hidden:**

| Model | Parameters | Context length | Availability |
|---|---|---|---|
| Kronos-mini | 4.1M | 2048 | public |
| Kronos-small | 24.7M | 512 | public |
| Kronos-base (chosen) | 102.3M | 512 | public, matches code's current default |
| Kronos-large | 499.2M | 512 | **not yet publicly released** |

Source: [NeoQuasar/Kronos-mini](https://huggingface.co/NeoQuasar/Kronos-mini),
[NeoQuasar/Kronos-small](https://huggingface.co/NeoQuasar/Kronos-small),
[NeoQuasar/Kronos-base](https://huggingface.co/NeoQuasar/Kronos-base) on
Hugging Face. `Kronos-large` exists as a published spec but its weights
are not publicly released, so it isn't actually a selectable option
right now regardless of preference. Between the three real choices,
`Kronos-base` (matching the code's current default) was kept —
`Kronos-mini` is notably smaller but has a longer context window (2048
vs. 512), which is an interesting trade-off worth trying in the future
if longer-context forecasting becomes relevant, but not chosen now.
**Future work**: try `mini`/`small` as a speed/accuracy trade-off study
once `base`'s real results and real cost are known — same open-ended
future-work framing already used for Chronos's untried sizes.

**Why directional accuracy instead of a quantile band:** unlike Chronos,
which explicitly outputs p10/median/p90 from its forecast distribution,
this codebase's Kronos integration only surfaces one point forecast per
step even though the model samples 3 times internally (`sample_count=3`)
— the sampling isn't exposed as a band in the code's output. Rather than
reaching into the model internals to reconstruct a band that isn't part
of this integration's actual interface, directional accuracy is used —
the same principle already applied to DLinear/iTransformer/Kalman: use
the model's real, exposed output, don't invent or reconstruct something
it doesn't actually give us.

**Why store full OHLC per step instead of just close:** the model
already forecasts the whole candle, not just a closing price — same
reasoning as iTransformer's all-5-channels decision: real, free model
output shouldn't be discarded just because only one field (`close`) is
needed for the hit definition.

**Why add RMSE alongside directional accuracy:** directional accuracy is
a strict binary (up/down correct or not) — appropriate as the primary
metric since expecting an exact price match would be an impossibly high
bar for any real forecaster. But collapsing every miss into the same
"wrong" bucket hides real information: a forecast that missed the
direction by a few cents is a very different outcome than one that
missed by several dollars. RMSE captures that closeness/magnitude
dimension without requiring or expecting exact matches — same principle
already applied when GARCH got a continuous QLIKE/MSE metric alongside
its own directional-accuracy secondary metric, just applied in the
opposite priority order here (RMSE secondary, direction primary) since
direction is the more actionable signal for this angle's use case.

**Why fallback-proxy handling isn't designed for here:** identical
reasoning to Chronos — the real pretrained weights are confirmed present
and loaded in this deployment, so building special handling for a path
that isn't expected to trigger would be solving a problem that doesn't
exist yet. If that changes, this would need revisiting (same as it would
for Chronos).

**Open/unresolved:** actual compute cost of running `Kronos-base`
(102M params, with internal 3x sampling per call) across a full
walk-forward backtest, especially at 1min/5min timeframes, has not been
benchmarked — same category of open caveat as ARIMA/Chronos/iTransformer,
needs real measurement before committing to a refit cadence for the
finer timeframes.
