---
name: angle-29-tips_regime_aware_transformer
status: decided
purpose: discussion and enhancement proposal for the `tips_regime_aware_transformer` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/`.
---

# 29 — tips_regime_aware_transformer

**Title (from spec.yaml):** TIPS Regime-Aware Transformer Forecast

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/`.
- Genuinely trained-from-scratch every run, same category as DLinear/
  LSTM/LPatchTST/PatchTST/TFT/iTransformer — no `model_backend` field,
  no pretrained/fallback question.
- **A real, confirmed paper exists — but the code implements something
  genuinely different from it, not just a scoped-down version.**
  Verified `arXiv:2603.16985`, *"Integrating Inductive Biases in
  Transformers via Distillation for Financial Time Series Forecasting"*
  (Den, Chen, Vincent, Chang) — real, confirmed authors/abstract. The
  paper's actual TIPS method is **knowledge distillation**: multiple
  specialized *teacher* Transformers, each trained via attention masking
  to encode a *different* inductive bias (**causality, locality,
  periodicity** — not "momentum vs. mean-reversion"), distilled into one
  efficient *student* Transformer with "regime-dependent alignment across
  inductive biases." Reported results (38% of the inference compute of
  ensemble baselines, statistically significant excess returns) are for
  *that* architecture.
- **What the code actually builds**: a single shared transformer encoder
  with **two linear output heads**, gated by a simple lag-1 return
  autocorrelation statistic into "momentum" (autocorr ≥ 0) or
  "mean_reversion" (autocorr < 0) — no teacher models, no distillation,
  no causality/locality/periodicity biases. This is a real, legitimate,
  working regime-conditioned model in its own right — but it is not an
  implementation of the cited paper's method, despite the code's own
  docstring framing it as satisfying "the spec." This is a bigger gap
  than, say, iTransformer's channel-vs-asset workaround (which preserves
  the paper's actual attention mechanism, just applied to a different
  input axis) — here, the core mechanism itself (multi-teacher
  distillation) isn't present at all.
- **Decision: build and backtest the code's real, simpler design as its
  own thing — "TIPS-inspired regime-gated forecaster," not "TIPS."**
  The paper's reported benchmark numbers are **not** carried over as a
  comparison target for this angle, since they describe a materially
  different architecture — doing so would repeat the exact kind of
  unverified-claim problem already caught and corrected for LSTM/
  LPatchTST/TFT, just one level deeper (misattributing a whole paper's
  results to a different model, not just citing the wrong number from
  the right paper).
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

This angle gets freshly trained from scratch every time it runs — it
first checks whether the stock's recent moves have been trending
(momentum) or reversing (mean-reversion) using a simple statistical
test, then routes its forecast through one of two differently-tuned
prediction heads depending on which regime it detects — a real,
distinct design in its own right, even though it's a simpler cousin of
the more elaborate multi-teacher method its name references.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable — genuinely trained-from-scratch every step | same as DLinear/LSTM/LPatchTST/PatchTST/TFT/iTransformer |
| Architecture | shared transformer encoder (`D_MODEL=16, NHEAD=2, 1 layer`) → pooled → regime-gated selection between two linear heads (`momentum_head`, `mean_reversion_head`) via `torch.where` | code default, kept as-is — this is the real, working design being backtested, framed accurately as "TIPS-inspired," not "TIPS" |
| Regime detection | lag-1 autocorrelation of returns over a trailing 20-bar window (code's `REGIME_WINDOW`); `autocorr ≥ 0` → momentum, `< 0` → mean_reversion | code default, kept as-is — a real, legitimate, simple regime heuristic, not the paper's causality/locality/periodicity teacher framework |
| Lookback window | 24 candles (code default `LOOKBACK`, kept as-is) | |
| Min observations | 120 candles (code's own real, derived floor: lookback + regime window + ~20 training windows) | **kept as-is, not adjusted toward the general N=100 convention** — this floor already exceeds 100 and is directly derived from the model's actual data requirements, not an arbitrary default like the ones that got raised elsewhere |
| Training epochs | 50 (code default, kept as-is) | real Adam (lr=0.01) training every call |
| Random seed | fixed at 42 for the whole backtest | same reproducibility rationale as every other trained-from-scratch angle |
| Forecast horizon | 1 step ahead | matches the code's actual architecture (single next-value linear heads), same "kept native" treatment as LPatchTST/LSTM/PatchTST/TFT |
| Hit definition | directional accuracy — predicted direction (up/down/flat) matches actual next-candle direction | no confidence interval in this model's output, same reasoning as every other point-forecast trained-from-scratch angle |
| Secondary evaluation metric | RMSE and MAE between `forecast_price` and actual close | same "how close in dollars" addition used across every point-output angle |
| **New: results split by detected regime** | in addition to the overall directional-accuracy/RMSE/MAE numbers, also report them separately for rows where `regime == momentum` vs. `regime == mean_reversion` | the natural, on-topic validation question for *this specific angle*: is the regime-gating actually earning its keep — does each head perform well specifically within the regime it's supposed to specialize in — not something borrowed from another angle's pattern |
| Diagnostic fields stored | `regime`, `regime_autocorr`, `n_momentum_windows`, `n_mean_reversion_windows` (all already real, computed code output) | kept as-is — real, free diagnostic output already present in the code, not discarded |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as every other trained-from-scratch angle |
| Weight storage | every walk-forward step's trained weights saved, `weights_ref` pointer on the row | same pattern as DLinear/LSTM/LPatchTST/PatchTST/TFT/iTransformer |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other trained-from-scratch angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest, same metrics | same rationale as other angles; DLinear/LSTM (non-regime-aware trained-from-scratch angles) also serve as an implicit "no regime conditioning" comparison point |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | not expected to be a concern | small transformer (d_model=16, 1 layer), similar cost class to PatchTST/TFT |
| Benchmark to compare against | **none carried over from the source paper** | the paper's reported results describe a materially different (multi-teacher distillation) architecture — applying them here would misattribute results to a model that wasn't actually tested |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
n_train_windows: 62
lookback: 24
regime_window: 20
regime: momentum
regime_autocorr: 0.18
n_momentum_windows: 38
n_mean_reversion_windows: 24
train_loss: 0.0102
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

**After aggregation (queryable key, split by regime):**

```
NY-MARKETHOURS-1330-2000-1D-MOMENTUM = 57.2% directional accuracy, RMSE 0.61 (n=524)
NY-MARKETHOURS-1330-2000-1D-MEAN_REVERSION = 53.8% directional accuracy, RMSE 0.74 (n=388)
```

(Illustrative — whether the momentum head genuinely outperforms in
momentum-labeled windows, and vice versa, is a real, measured finding
once this runs, not assumed in advance.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same shape as DLinear/LSTM/LPatchTST/
  PatchTST/TFT — one row per walk-forward step, fully tagged, plus
  regime/autocorrelation fields and a `weights_ref` pointer.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  combinations precomputed after each run, each carrying `n`, directional
  accuracy, RMSE, MAE — **plus the same breakdown split by regime label**,
  each with its own `n`.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.
- **Weights artifact store**: same convention as the other
  trained-from-scratch angles.

Reuses the exact same storage patterns already established across the
trained-from-scratch angle set, with one addition (the regime split)
specific to what this angle actually claims to do differently.

## 6) What we will achieve / how to use it

- An honest answer to whether this angle's actual mechanism (regime-gated
  dual heads) earns its keep — does each head genuinely perform better
  within its own claimed regime, not just an aggregate accuracy number
  that could hide one head carrying the other.
- A direct comparison against DLinear/LSTM (no regime conditioning at
  all) and LPatchTST/PatchTST (a different kind of structural
  augmentation) on the same data — a real answer to "does regime-gating
  add value over a plain trained-from-scratch model," parallel to the
  LPatchTST-vs-PatchTST ablation already set up for the patch-based
  angles.
- A corrected, honest record of what this angle actually is — preventing
  a future reader from assuming the source paper's reported 38%-compute-
  savings/excess-returns results apply here, when they describe a
  materially different architecture.

## 7) Deeper rationale

**Why this gets built and backtested as its own design rather than
either (a) implementing the real multi-teacher TIPS or (b) dropping the
angle:** building the paper's actual method (multiple specialized
teacher Transformers plus a distillation training loop) is a
substantially larger undertaking than any other angle in this
trained-from-scratch set — a different scope of work, not a parameter
decision. The code's simpler regime-gated design is still a real,
coherent, legitimate architecture worth testing on its own merits; the
right move is testing it honestly under its own name, not discarding
working code or silently overselling it as the paper's method.

**Why no benchmark comparison is carried over from the paper:** the
paper's reported numbers characterize teacher-student distillation
across causality/locality/periodicity biases — a different model
entirely. Citing those figures as a target for this angle would repeat,
at a larger scale, the exact mistake already caught and fixed for LSTM/
LPatchTST/TFT (using a real paper's numbers for a model that doesn't
match what was actually tested) — except those three at least shared the
same core architecture as what was benchmarked; here the core mechanism
itself differs.

**Why the regime split is the one new metric proposed for this angle
specifically:** every other trained-from-scratch angle's enhancements
(RMSE/MAE, weights storage, timeframe widening) are generic, reusable
patterns. The regime split is different — it's the one metric that
directly tests *this angle's specific claim* (that conditioning on
detected regime helps), so it belongs here and nowhere else.

**Why N stays at the code's real 120 instead of being touched:** unlike
the other N-adjustments in this project (which raised arbitrary, too-low
defaults toward a consistent N=100), this floor is already a real,
derived number *above* 100, tied directly to what the model's own
lookback + regime window + training-sample requirements actually need.
Changing it would be arbitrary in the other direction.

**Open/unresolved:** whether the simple autocorrelation-based regime
split (momentum vs. mean-reversion) is itself a good regime detector is
an open, empirical question this backtest will help answer via the
regime-split comparison — not assumed to be correct or incorrect in
advance. Also open: whether a future pass should attempt the paper's
actual multi-teacher distillation method as a separate, new angle,
rather than folding it into this one — noted as a possibility, not
decided here.
