---
name: angle-14-lstm
status: decided
purpose: discussion and enhancement proposal for the `lstm` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lstm/`.
---

# 14 — lstm

**Title (from spec.yaml):** LSTM Sequential Forecast

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lstm/`
- Genuinely trained-from-scratch every run, same category as DLinear/
  iTransformer/LPatchTST — no `model_backend` field exists in this
  angle's output; not a pretrained/fallback situation at all.
- Plain, classical single-layer LSTM — no patching, no hybrid branch
  (unlike `lpatchtst`, which shares this project's `PatchEncoderBranch`
  alongside its own LSTM branch). This is the simplest of the
  trained-from-scratch angles.
- **Source claim corrected, same discrepancy pattern as `lpatchtst`.**
  The project's own planning note (`19-lstm.md`) reported "~51%
  directional accuracy," flagged there as "not independently
  re-verified." Traced to the same paper found for LPatchTST —
  Saly-Kaufmann, Wood, Peter-Calliess, Zohren, *"Deep Learning for
  Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted
  Performance,"* arXiv:2603.01820 (March 2026) — which reports plain
  LSTM's real hit rate as **55.4%** (Sharpe 1.32), not ~51%. This paper's
  Table 2 covers DLinear, LSTM, PatchTST, LPatchTST, iTransformer, and
  TFT together — very likely the single actual source behind this
  project's whole "six trained-from-scratch architectures" survey
  comparison, worth a quick cross-check when `patchtst` (20) and `tft`
  (26) come up, and worth double-checking against `itransformer` (09,
  already decided) too.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

LSTM is a small model that gets freshly trained from scratch every time
it runs — it reads a stock's recent prices one step at a time, like
reading a sentence word by word while remembering what came before, and
uses what it remembers to guess the next price and whether it's headed
up or down.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable — genuinely trained-from-scratch every step | confirmed no `model_backend` field in code's output, same as DLinear/LPatchTST |
| Architecture | single-layer LSTM (hidden_size=16) → 1 linear head | code default, kept as-is — the plain recurrent baseline, no patching/hybrid branch |
| Lookback window | 30 candles (code default `LOOKBACK`, kept as-is) | |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_BARS = 80`), same consistency move as ARIMA/DLinear/LPatchTST's N=100 |
| Training epochs | 60 (code default, kept as-is) | real Adam (lr=0.01) gradient-descent training happens every call — cheap, small model (well under 50k params) |
| Random seed | fixed at 42 for the whole backtest | same reproducibility rationale as DLinear/iTransformer/LPatchTST |
| Forecast horizon | 1 step ahead | matches the code's actual architecture (single-value linear head off the final hidden state) and the paper's own 55.4%-hit-rate benchmark, which is itself a 1-step number — same reasoning as LPatchTST, kept native rather than extended |
| Hit definition | directional accuracy — predicted direction (up/down/flat, ±0.0001 deadband, code's own `_direction()` function) matches actual next-candle direction | same reasoning as DLinear/LPatchTST — point forecast + threshold, no confidence interval, so direction match is the natural, code-grounded hit definition |
| Secondary evaluation metric | RMSE and MAE between `forecast_price` and actual close | same "how close in dollars" addition made for Kronos/lag_llama/LPatchTST |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as every other angle |
| Weight storage | every walk-forward step's trained weights saved, `weights_ref` pointer on the row | same pattern as DLinear/LPatchTST — model small enough (well under 50k params) that saving every step's weights is cheap |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest, same metrics | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | not expected to be a concern | small model (16 hidden units, 60 epochs on ~50-70 windows) — comparable to DLinear/LPatchTST's cheap training cost |
| Benchmark to compare against | 55.4% directional accuracy (corrected, see §1) | this backtest's own measured hit rate is checked against this figure, not the originally-miscited ~51% |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
n_train_windows: 70
lookback: 30
hidden_size: 16
train_loss: 0.0131
forecast_price: 142.60
forecast_return: 0.00210
direction: up
actual_close: 142.80
actual_direction: up
hit: true
close_sq_error: 0.04
close_abs_error: 0.20
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
NY-MARKETHOURS-1330-2000-1D = 56.1% directional accuracy, RMSE 0.68, MAE 0.52 (n=912 forecasts)
```

(A real measured number to compare against the corrected 55.4% paper
benchmark — not assumed to land exactly on it.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as DLinear/LPatchTST — one
  row per walk-forward step, fully tagged, plus a `weights_ref` pointer
  field.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  combinations precomputed after each run, each carrying `n`, directional
  accuracy, RMSE, MAE — aggregate-only values.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.
- **Weights artifact store**: every trained model's weights saved as a
  small separate file, named `{symbol}_{timeframe}_{candle_ts}.pt`,
  referenced via `weights_ref` — same pattern already established for
  DLinear/LPatchTST, reused as-is.

Reuses the exact same 3-layer tagging architecture and weights-artifact
pattern already defined for DLinear/LPatchTST — no new storage design
needed for this angle.

## 6) What we will achieve / how to use it

- A real, backtested directional-accuracy number per timeframe/session/
  day, checked directly against the corrected 55.4% paper benchmark.
- The cleanest possible baseline comparison against `lpatchtst` — since
  LPatchTST is literally this same LSTM architecture plus a patch branch
  bolted on, this angle is what answers "how much does the patch branch
  actually add" once both are built and backtested on the same data.
- RMSE/MAE alongside directional accuracy for the "how close in dollars"
  answer, same as the other trained-from-scratch angles.
- Every trained step's weights kept and referenceable, same as DLinear/
  LPatchTST.
- A genuine baseline comparison (vs. naive random-walk) to check this
  small recurrent model earns its keep.

## 7) Deeper rationale

**Why the corrected 55.4% figure matters, and why it strengthens the
"lightweight models can compete" framing:** the original ~51% claim
would have made LSTM look barely better than a coin flip. The real
number (55.4%, Sharpe 1.32) is meaningfully stronger, and directly
supports the separate observation already noted in this project's own
TIPS angle discussion that "lightweight LSTM/GRU/Mamba often beat huge
transformers on financial data" — in the same source paper's table,
plain LSTM actually beats plain PatchTST (54.1%) and iTransformer
(52.9%) on hit rate, despite being architecturally much simpler. Using
the wrong (lower) figure would have understated how strong this
"simple baseline" actually is.

**Why native 1-step horizon instead of extending to 5 steps:** identical
reasoning to LPatchTST — the code's linear head produces exactly one
value from the final LSTM hidden state, and the paper's 55.4% figure is
itself a 1-step number. Recursively feeding forecasts back in or
retraining a multi-output head would mean testing a different model than
the one actually verified against the source.

**Why directional accuracy instead of CI-coverage:** identical reasoning
to DLinear/LPatchTST — no confidence interval anywhere in the code's
output, so direction match is the natural, code-grounded hit definition
rather than an invented threshold.

**Why RMSE/MAE alongside directional accuracy:** same reasoning as
Kronos/lag_llama/LPatchTST — a binary hit/miss hides how far off a call
actually was, in either direction.

**Why N=100 instead of the code's current 80:** same consistency
reasoning as every other raised-floor angle, for fair cross-timeframe/
cross-angle comparison.

**Why store every step's weights instead of sampling:** same reasoning
as DLinear/LPatchTST — small model, negligible storage cost, full
reproducibility of any historical prediction.

**Open/unresolved:** same caveat as LPatchTST — the corrected 55.4%
figure comes from the source paper's own asset universe (futures across
commodities/equities/bonds/FX, 2010-2025), not our own Alpaca equity
data or timeframe mix, so it's a reference point to compare against, not
a guarantee of what this backtest will measure. Also flagging again: the
same source paper likely underlies `itransformer`'s (already decided)
and the not-yet-discussed `patchtst`/`tft` benchmark claims too — worth
a cross-check pass once those are reached, given 2-for-2 of the figures
checked so far turned out to be wrong.
