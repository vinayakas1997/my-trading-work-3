---
name: angle-26-tft
status: decided
purpose: discussion and enhancement proposal for the `tft` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/tft/`.
---

# 26 — tft

**Title (from spec.yaml):** TFT Temporal Fusion Transformer (Quantile Forecast)

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/tft/`.
- Genuinely trained-from-scratch every run, same category as DLinear/
  LSTM/LPatchTST/PatchTST/iTransformer — no `model_backend` field, no
  pretrained/fallback question.
- **Verified faithful to the real paper** (Lim et al., *"Temporal Fusion
  Transformers for Interpretable Multi-horizon Time Series Forecasting,"*
  International Journal of Forecasting 2021, arXiv:1912.09363): the
  code's `VariableSelection` module (softmax-gated per-feature weighting)
  matches the paper's variable-selection network; the LSTM encoder +
  `MultiheadAttention` pooling matches the paper's sequence-processing +
  interpretable-attention combination; the median-plus-softplus-deltas
  head construction is a real, standard fix that **guarantees
  P10 ≤ P50 ≤ P90 by construction** (no quantile crossing), trained via
  genuine pinball loss — a faithful, honestly-scoped "TFT-lite," not a
  superficial reskin.
- **Honestly disclosed, not silently dropped**: the code's own docstring
  states static covariates and known-future inputs (e.g. earnings
  calendar, sector) from the original spec are not modeled, because
  `bars`/`news` as passed to `compute()` don't carry that schema —
  correctly scoped to what's actually available, not glossed over.
- **Benchmark claim corrected — third instance of the same pattern
  already caught for `lstm` and `lpatchtst`.** The project's own
  planning note (`22-tft.md`) claims "~53% directional accuracy,"
  flagged there as "not independently re-verified." The same source
  paper already identified for LPatchTST/LSTM (Saly-Kaufmann et al.,
  arXiv:2603.01820, Table 2) reports TFT's real hit rate as **58.4%**
  (Sharpe 2.20) — higher than claimed, same direction of error as the
  other two corrections. This is now a consistent pattern across all
  three trained-from-scratch angles checked against this paper.
- **Closes an open item from the `lstm`/`lpatchtst` discussions**: both
  of those files flagged `itransformer` (angle 09, already decided) as
  needing a cross-check against this same benchmark table. Checked now —
  `09-itransformer.md` does **not** cite any figure from
  arXiv:2603.01820; it correctly cites the actual iTransformer paper
  (Liu et al., ICLR 2024, arXiv:2310.06625) for methodology only, with no
  finance-benchmark claim to correct. No change needed there — this loop
  is now closed.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

TFT is a small model that gets freshly trained from scratch every time it
runs — it first learns which of six engineered signals (recent return,
5-day return, two moving-average ratios, short-term volatility, high-low
range) matter most right now, feeds the weighted signals through a
memory-based encoder and self-attention, then produces not just one
guess but a realistic range (P10 to P90) for the next price move,
guaranteed to never contradict itself (the low end can never end up above
the high end).

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable — genuinely trained-from-scratch every step | same as DLinear/LSTM/LPatchTST/PatchTST/iTransformer |
| Architecture | variable-selection gate → LSTM (hidden=16) → self-attention (2 heads) → median head + softplus delta heads → P10/P50/P90 | code default, kept as-is — faithful lightweight TFT, verified against the real paper |
| Features | `ret_1, ret_5, sma_ratio_5, sma_ratio_21, vol_5, high_low_range` (code default, kept as-is) | six engineered signals, the input the variable-selection network actually operates over |
| Lookback window | 30 candles (code default `LOOKBACK`, kept as-is) | |
| Min observations (N) | 100 candles | raised from the code's current floor (`MIN_BARS = 90`), same consistency move as every other trained-from-scratch angle |
| Training epochs | 60 (code default, kept as-is) | real Adam (lr=0.01) training via genuine pinball loss every call |
| Random seed | fixed at 42 for the whole backtest | same reproducibility rationale as every other trained-from-scratch angle |
| Forecast horizon | 1 step ahead | matches the code's actual architecture (single next-step quantile triple) and the corrected 58.4%-hit-rate benchmark, which is itself a 1-step number — same "kept native" reasoning as LPatchTST/LSTM/PatchTST |
| Uncertainty band | P10/P50/P90, non-crossing by construction | code's real, exposed output — genuinely more principled than lag_llama/moirai's post-hoc Gaussian bands, since crossing is architecturally impossible here, not just empirically rare |
| Primary evaluation metric | CI-coverage: actual close falls inside [P10, P90] (an 80% band) | same principle as lag_llama/moirai — uses the model's own real, guaranteed-valid quantile output |
| Secondary evaluation metric | directional accuracy on P50 vs. actual next-candle direction | matches the source paper's own reported metric (hit rate), for direct comparability to the corrected 58.4% figure |
| Tertiary evaluation metric | pinball loss on held-out backtest steps (not training loss) | this is literally the model's own training objective — evaluating it out-of-sample is the most natural calibration-quality check, same metric family already used for lag_llama/moirai |
| Quaternary evaluation metric | RMSE and MAE between P50 and actual close | same "how close in dollars" addition used across every point/quantile-output angle so far |
| Diagnostic fields stored | `variable_selection_weights` (per-feature weights, the model's real interpretability output), P10/P50/P90, `train_loss` | the model already computes per-feature weights as part of its normal forward pass — this is the one trained-from-scratch angle with a genuine interpretability signal, discarding it would throw away real, free, distinctive output |
| Backtest method | walk-forward (rolling: train fresh, forecast, check, slide, repeat) | same method as every other trained-from-scratch angle |
| Weight storage | every walk-forward step's trained weights saved, `weights_ref` pointer on the row | same pattern as DLinear/LSTM/LPatchTST/PatchTST/iTransformer |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | widened from the spec's current 1D-only, same as every other trained-from-scratch angle |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Baseline comparison | naive random-walk (forecast = last close), same backtest, same metrics | same rationale as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Compute cost | open/unbenchmarked, likely comparable to iTransformer | real self-attention + LSTM per training step, more expensive than DLinear's pure-linear model, similar cost class to iTransformer — same honesty caveat about full 1min/5min feasibility, not yet measured |
| Benchmark to compare against | 58.4% directional accuracy, Sharpe 2.20 (corrected, see §1) | this backtest's own measured hit rate is checked against the corrected figure, not the originally-miscited ~53% |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
n_train_windows: 45
lookback: 30
train_loss: 0.00187
forecast_price_p10: 141.10
forecast_price_p50: 142.55
forecast_price_p90: 144.30
actual_close: 142.80
direction: up
actual_direction: up
hit: true
in_band: true
pinball_loss: 0.09
close_sq_error: 0.06
close_abs_error: 0.25
variable_selection_weights: {ret_1: 0.31, ret_5: 0.12, sma_ratio_5: 0.19, sma_ratio_21: 0.08, vol_5: 0.22, high_low_range: 0.08}
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
NY-MARKETHOURS-1330-2000-1D = 59.8% directional accuracy, 82% CI-coverage,
  avg pinball 0.11, RMSE 0.64, MAE 0.49 (n=912 forecasts)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: same flat, single-row-per-step shape as
  DLinear/LSTM/LPatchTST/PatchTST/iTransformer (not the nested
  multi-horizon-step pattern used for the 5-step angles, since this is a
  1-step forecaster) — full quantile triple, hit/in-band flags,
  pinball/sq-error/abs-error, variable-selection weights, `weights_ref`.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe
  combinations precomputed after each run, each carrying `n`, directional
  accuracy, CI-coverage, average pinball loss, RMSE, MAE.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle.
- **Weights artifact store**: same convention as DLinear/LSTM/LPatchTST/
  PatchTST/iTransformer — `{symbol}_{timeframe}_{candle_ts}.pt`,
  referenced via `weights_ref`.

Reuses the exact same storage patterns already established across the
trained-from-scratch angle set — no new design needed.

## 6) What we will achieve / how to use it

- A real, backtested comparison against the corrected 58.4% paper
  benchmark, plus a direct comparison against every other
  trained-from-scratch angle (DLinear, LSTM, LPatchTST, PatchTST,
  iTransformer) on the same data, same date range, same tagging.
- The only trained-from-scratch angle in this set with a genuine
  interpretability signal — tracking `variable_selection_weights` over
  time and across sessions/regimes could reveal, e.g., whether the model
  leans on volatility features more during turbulent periods and on
  return/trend features during calm ones, a question none of the other
  point-forecast angles can answer.
- A more principled uncertainty band than lag_llama/moirai's fallback
  proxies — non-crossing by construction rather than by post-hoc
  clipping — giving a genuinely trustworthy CI-coverage comparison point
  among the trained-from-scratch set.
- Closes the benchmark-verification loop opened by the LSTM/LPatchTST
  discussions — all three trained-from-scratch angles checked against
  arXiv:2603.01820 now have corrected figures, and `itransformer` is
  confirmed clean.

## 7) Deeper rationale

**Why the real-paper cross-check mattered here specifically:** TFT's
whole architecture is a composition of several named, specific pieces
(variable selection network, gated residual connections, LSTM,
interpretable attention, monotone quantile loss) — a "TFT-lite" claim is
only meaningful if those pieces are actually present and doing what the
paper describes, not just borrowing the name. Verifying line-by-line
against the real paper's component list (rather than trusting the
code's own docstring claims at face value) confirmed this is a real,
faithful adaptation, not a superficial one — worth the extra check given
how specific the architectural claims are.

**Why the corrected 58.4% figure, and why the pattern across three
angles matters:** same reasoning as LSTM/LPatchTST — the original ~53%
claim understated a genuinely strong result (TFT is tied for the
second-best Sharpe in the source paper's whole table, right behind
LPatchTST). Three-for-three miscited figures, all in the same direction
(underselling the real performance), suggests whatever produced this
project's internal survey table systematically mishandled this
particular paper's numbers — worth keeping in mind if any other angle
later turns out to reference the same source.

**Why closing the `itransformer` cross-check here, not as a separate
pass:** it was flagged as an open item in two prior files specifically
so it wouldn't get forgotten — checking it now, while directly reading
the same benchmark table again for TFT, was the natural, low-cost moment
to close it rather than deferring further.

**Why pinball loss is included despite already being the training
objective:** training loss alone only tells you the model fit its own
training data; evaluating pinball loss on held-out walk-forward steps is
what actually tests whether the learned quantiles generalize — the same
in-sample-vs-out-of-sample discipline used throughout this project
(e.g. `significance_model.py`'s chronological train/test split).

**Why `variable_selection_weights` is kept instead of discarded:** same
principle applied to every other angle with free diagnostic output
(DLinear's alpha/beta, iTransformer's 5 channels, Kronos's full OHLC) —
the model computes this as part of its normal forward pass at zero extra
cost, and it's the one genuinely distinctive, interpretable signal this
whole trained-from-scratch set produces.

**Open/unresolved:** compute cost across the finer timeframes (1min/5min)
is unmeasured, same caveat as iTransformer. The corrected 58.4% figure
comes from the source paper's own asset universe (futures, not
equities), so it remains a reference point, not a guarantee of what this
backtest measures on Alpaca data.
