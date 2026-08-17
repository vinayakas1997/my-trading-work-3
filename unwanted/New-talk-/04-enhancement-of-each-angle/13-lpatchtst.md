---
name: angle-13-lpatchtst
status: decided
purpose: discussion and enhancement proposal for the `lpatchtst` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/`.
---

# 13 — lpatchtst

**Title (from spec.yaml):** LPatchTST LSTM+PatchTST Hybrid Forecast

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/`
- Genuinely trained-from-scratch every run, same category as DLinear/
  iTransformer — no `model_backend` field exists in this angle's output
  at all, so there is no pretrained/fallback question to answer here.
- "L" is LSTM, not "lightweight" — confirmed from the code's own module
  docstring and `spec.yaml` title. Two branches on the same window: an
  LSTM branch, and a `PatchEncoderBranch` **imported directly from the
  `patchtst` angle's shared module** (`_patch_transformer.py`) — the same
  patching/attention core `patchtst` (angle 20) uses standalone, reused
  here as one branch of the hybrid rather than reimplemented.
- **Source claim corrected.** The project's own planning note
  (`23-lpatchtst.md`) reported "~54% directional accuracy, Sharpe
  2.31–2.32," flagged there as "not independently re-verified." Traced to
  a real paper — Saly-Kaufmann, Wood, Peter-Calliess, Zohren, *"Deep
  Learning for Financial Time Series: A Large-Scale Benchmark of
  Risk-Adjusted Performance,"* arXiv:2603.01820 (March 2026). The Sharpe
  figure checks out exactly (2.31–2.32), but **the ~54% directional
  accuracy figure does not belong to LPatchTST** — the paper reports
  LPatchTST's actual hit rate as **57.7%**; 54.1% is vanilla PatchTST's
  hit rate in the same paper's table. The two got crossed somewhere
  upstream of this project's notes. This file uses the corrected 57.7%
  figure as the benchmark to compare our own backtest against.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

LPatchTST is a small model that gets freshly trained from scratch every
time it runs — it reads a stock's recent prices two different ways at
once (once step-by-step like a memory, once broken into overlapping
chunks looked at all together), combines what both views learned, and
uses that to guess the very next price and whether it's headed up or
down.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable — genuinely trained-from-scratch every step | confirmed no `model_backend` field in code's output; not a pretrained/fallback situation at all, unlike lag_llama |
| Architecture | LSTM branch (hidden=16) + `PatchEncoderBranch` (patch_len=8, stride=4, d_model=16, nhead=2, 1 transformer layer, shared with `patchtst`) → concatenated → 1 linear head | code default, kept as-is — this is the actual hybrid being tested, not a reimplementation |
| Lookback window | 32 candles (code default `LOOKBACK`, kept as-is) | matches the shared `PatchEncoderBranch`'s config so both angles' patch branch see the same window shape |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_BARS = 90`), same consistency move as ARIMA/DLinear's N=100 |
| Training epochs | 50 (code default, kept as-is) | real Adam (lr=0.01) gradient-descent training happens every call — cheap, small model |
| Random seed | fixed at 42 for the whole backtest | same reproducibility rationale as DLinear/iTransformer — isolates data-driven differences from init noise |
| Forecast horizon | 1 step ahead | matches the code's actual architecture (`make_windows(..., horizon=1)`, single-value linear head) and the paper's own 57.7%-hit-rate benchmark, which is itself a 1-step number; kept native rather than extended, to stay faithful to both the verified code and the verified source |
| Hit definition | directional accuracy — predicted direction (up/down/flat, ±0.0001 deadband, code's own `direction()` function) matches actual next-candle direction | same reasoning as DLinear — the model outputs a point forecast + threshold, no confidence interval, so direction match is the natural, code-grounded hit definition |
| Secondary evaluation metric | RMSE and MAE between `forecast_price` and actual close | same "how close in dollars" addition made for Kronos and lag_llama — directional accuracy alone doesn't say how far off a wrong (or right) call actually was |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as every other angle — a fresh model trained at every step, not reused |
| Weight storage | every walk-forward step's trained weights saved, `weights_ref` pointer on the row | same pattern as DLinear — model is small enough (LSTM hidden=16 + patch branch d_model=16) that saving every step's weights is cheap and keeps every historical prediction fully reproducible |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest, same metrics | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | not expected to be a concern | small model (d_model=16, 50 epochs on ~58 windows at MIN_BARS=100/lookback=32) — comparable to DLinear's cheap training cost, not in Kronos/Chronos's transformer-forward-pass cost class |
| Benchmark to compare against | 57.7% directional accuracy (corrected, see §1) | this backtest's own measured hit rate is checked against this figure, not the originally-miscited ~54% |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
n_train_windows: 58
lookback: 32
lstm_hidden_size: 16
n_patches: 7
train_loss: 0.0118
forecast_price: 142.55
forecast_return: 0.00175
direction: up
actual_close: 142.80
actual_direction: up
hit: true
close_sq_error: 0.0625
close_abs_error: 0.25
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
NY-MARKETHOURS-1330-2000-1D = 58.4% directional accuracy, RMSE 0.71, MAE 0.54 (n=912 forecasts)
```

(A real measured number to compare against the corrected 57.7% paper
benchmark — not assumed to land exactly on it.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as DLinear — one row per
  walk-forward step, fully tagged, plus a `weights_ref` pointer field.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  combinations precomputed after each run, each carrying `n`, directional
  accuracy, RMSE (`sqrt(mean(close_sq_error))`), and MAE
  (`mean(close_abs_error)`) — aggregate-only values, same rule as every
  other angle with RMSE/MAE.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.
- **Weights artifact store**: every trained model's weights saved as a
  small separate file, named `{symbol}_{timeframe}_{candle_ts}.pt`,
  referenced via `weights_ref` — same pattern DLinear already
  established, reused as-is here rather than redesigned.

Reuses the exact same 3-layer tagging architecture and weights-artifact
pattern already defined for DLinear — no new storage design needed for
this angle.

## 6) What we will achieve / how to use it

- A real, backtested directional-accuracy number per timeframe/session/
  day, checked directly against the corrected 57.7% paper benchmark —
  answering "does this hybrid actually perform the way the source paper
  claims on our own data," not the miscited ~54% figure.
- A direct comparison against standalone `patchtst` (angle 20, once
  discussed) — since both share the exact same `PatchEncoderBranch` code
  and window config, this is the cleanest possible test of "does adding
  the LSTM branch actually help over patching alone," the paper's own
  central claim.
- RMSE/MAE alongside directional accuracy — the same "how close in
  dollars" answer now standard across angles with point/quantile output.
- Every trained step's weights kept and referenceable, same as DLinear —
  useful for inspecting exactly what the model looked like behind any
  specific historical prediction.
- A genuine baseline comparison (vs. naive random-walk) to check this
  hybrid earns its keep beyond what a from-scratch NN might do by chance.

## 7) Deeper rationale

**Why the corrected 57.7% figure matters:** the original ~54% claim in
this project's own notes would have made LPatchTST look barely better
than a coin flip, and worse than what the same source paper reports for
*plain* PatchTST-without-LSTM (54.1%) — which would have undercut the
entire reason this angle exists (testing whether the hybrid is actually
worth the extra LSTM branch). The real number is meaningfully higher and
actually supports the hybrid's premise; using the wrong figure would have
set the wrong bar for what "working as expected" looks like once this
backtest runs for real.

**Why native 1-step horizon instead of extending to match the 5-step
angles:** two ways existed to get a 5-step number — recursively feeding
the model's own forecast back in as if it were real (compounding an
error the model was never trained or benchmarked to handle), or
retraining with a 5-output head (a different model than the one the
paper's 57.7% figure and the code actually describe). Both would mean
backtesting something other than the verified architecture. Keeping the
native 1-step horizon means the number we measure is directly comparable
to the paper's own reported figure, and the code doesn't need
architectural changes to test what's actually being claimed.

**Why directional accuracy instead of CI-coverage:** identical reasoning
to DLinear — the model outputs a single point forecast and a thresholded
direction, no confidence interval anywhere in its output. Direction match
is the natural, code-grounded hit definition rather than an invented
threshold.

**Why RMSE/MAE alongside directional accuracy:** same reasoning as
Kronos/lag_llama — a binary hit/miss hides how far off a wrong call was,
and says nothing about how close a *right* call actually landed. RMSE/MAE
on `forecast_price` vs actual close gives the plain-dollars answer.

**Why N=100 instead of the code's current 90:** same consistency
reasoning as every other raised-floor angle — a uniform warm-up window
across all angles keeps timeframe/session comparisons fair, even though
90 was itself a deliberately-derived number (enough raw bars to get ≥20
training windows at lookback=32), not an arbitrary floor.

**Why store every step's weights instead of sampling:** same reasoning
as DLinear — the model is small (LSTM hidden=16 + patch d_model=16),
so the storage cost of keeping every trained instance is negligible
against the value of being able to reproduce or inspect any specific
historical prediction later.

**Open/unresolved:** the corrected 57.7% figure comes from a single
2026 benchmark paper's own methodology (futures data across commodities/
equities/bonds/FX, 2010-2025) — not our own asset universe or timeframe
mix, so it's a reference point to compare against, not a guarantee of
what this backtest will actually measure on Alpaca equity data.
