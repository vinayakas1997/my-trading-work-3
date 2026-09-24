# 23 — tft

- **Angle id:** `tft`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/tft/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A small model trained from scratch on this ticker every run: a
variable-selection gate weights 6 engineered features, an LSTM encodes
the window, self-attention pools it, and three linear heads jointly
produce P10/P50/P90 next-step return quantiles. Per the shared benchmark
table already gathered for `lpatchtst`/`lstm`, this had the **highest
directional accuracy** of the six trained-from-scratch architectures
this codebase implements (58.4%, beating `lpatchtst`'s 57.7%). The
"interpretable" attention claim in the code comment doesn't hold as
written -- see F1.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | *(Real TFT)* Sharing **one value weight matrix** across all attention heads (instead of each head having its own) is *specifically required* for attention weights to be interpretable as per-feature importance. | [TF1] |
| A2 | *(Real TFT)* An LSTM **encoder-decoder** -- historical inputs into the encoder, known-future inputs into the decoder -- captures short-term temporal patterns before attention operates on top of it. | [TF1] |
| A3 | *(Code's own design)* Predicting a median plus two non-negative offsets (rather than three independently-trained quantile heads) guarantees P10 ≤ P50 ≤ P90 by construction -- avoiding "quantile crossing," a known failure mode of independently-trained quantile regression. | code's own comment; standard, widely-used fix, not separately sourced here |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | TFT vs. DeepAR/ConvTrans/Seq2Seq/MQRNN, "Volatility" dataset (OMI realized library: daily realized volatility of 31 stock indices from intraday data, plus daily returns), 252-day lookback, 5-day horizon | TFT's P50 quantile loss 0.039 (best; MQRNN 0.042, DeepAR 0.050) and P90 loss 0.020 (best; MQRNN 0.021, DeepAR 0.024) -- roughly 7-9% better than the next-best baseline. | [TF1] |
| R2 | Shared benchmark table already gathered for `lpatchtst`/`lstm` (daily futures, 2010-2025) | TFT: Sharpe 2.20, hit rate **58.4%** -- highest directional accuracy of the six architectures in that table, though second on Sharpe to the LSTM+PatchTST hybrid's 2.32. | [LP1] (already opened for [12-lpatchtst-angle.md](12-lpatchtst-angle.md)) |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Attention is plain `nn.MultiheadAttention` -- PyTorch's standard implementation, where **each head has its own separate value projection**. The code comment calls this "the 'interpretable multi-head attention' piece." | The paper is explicit and specific: "different values are used in each head [so] attention weights alone would not be indicative of a particular feature's importance. As such, we modify multi-head attention to share values in each head" -- a single shared value matrix is exactly what makes TFT's attention interpretable [TF1]. | **Real architecture-fidelity gap, precisely the opposite failure the paper names.** Standard `nn.MultiheadAttention` is exactly the "different values per head" case the paper says breaks interpretability. `variable_selection_weights` (from the separate gating network) is a genuinely interpretable output here, but the attention mechanism itself isn't the interpretable variant the comment claims it implements. |
| F2 | This angle's real target is **next-step return**, forecast at P10/P50/P90. | TFT's one directly financial, real benchmark result (R1) is for a different target variable: **realized volatility**, not returns, using a 252-day lookback and 5-day horizon [TF1]. | **The strongest published evidence for TFT on financial-style data doesn't transfer directly to what this angle predicts.** Unlike `dlinear`/`itransformer`/`patchtst`/`moment` (whose only financial evaluation was weak or explicitly excluded), TFT genuinely does have a strong, real financial-domain result -- but for volatility, with far more context (252 days vs. this angle's `LOOKBACK=30`) and a longer horizon (5 days vs. 1 step) than this implementation uses. |
| F3 | Pinball (quantile) loss: `max((q-1)*err, q*err)` where `err = target - pred`. | Standard pinball loss definition: `L_q(y, ŷ) = max(q(y-ŷ), (q-1)(y-ŷ))`. | **Correctly implemented**, verified by direct algebraic comparison -- mathematically identical to the textbook formula. |
| F4 | Median-plus-softplus-deltas head construction guarantees `P10 ≤ P50 ≤ P90` by architecture, not by post-hoc sorting. | -- (standard, widely-used technique, not separately sourced) | Sound engineering -- avoids quantile crossing without needing a corrective step after training. |
| F5 | No static covariates, no known-future inputs, no separate encoder/decoder split -- one LSTM encoder only. Explicitly disclosed in both the module docstring and `spec.yaml`. | Real TFT is an encoder-decoder specifically to handle known-future inputs (e.g. a known future earnings date) separately from historical ones [TF1]. | **Honest, already-disclosed simplification**, consistent with what `compute()` actually has access to (`bars`/`news`, no calendar/static schema) -- not a hidden gap, and the single-encoder design is the correct simplification given that known-future inputs were never going to be modeled here. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_return_p10/p50/p90` | Quantile forecasts of the next-step return. |
| `forecast_price_p10/p50/p90` | Same, converted to price via `last_close * (1 + return)`. |
| `direction` | `up`/`down`/`flat` from the sign of `forecast_return_p50` only. |
| `last_close` | Last actual close the model saw. |
| `lookback` | Always `30`. |
| `variable_selection_weights` | Dict of the 6 engineered features (`ret_1`, `ret_5`, `sma_ratio_5`, `sma_ratio_21`, `vol_5`, `high_low_range`) to their learned softmax weight at the final time step -- the one genuinely interpretable output this angle produces (see F1). |
| `n_train_windows` | How many 30-bar training examples it learned from. |
| `train_loss` | Final training pinball loss -- fit quality, not forecast accuracy. |
| `n_observations` | How many bars were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_BARS` (100) bars, or fewer than 15 training windows after feature engineering/windowing -- both reasons share this one status (same pattern as `dlinear`/`itransformer`/`lpatchtst`/`lstm`/`patchtst`). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What real TFT adds over a plain attention model.** Three specific
pieces, per the paper: a variable-selection network that learns
per-feature importance at each time step (this angle implements this
correctly, per-feature softmax weights, genuinely interpretable); an
LSTM encoder-decoder that separates historical from known-future inputs
(this angle correctly and honestly drops the decoder half, since it has
no known-future data to feed it); and "interpretable" multi-head
attention, specifically engineered -- sharing one value matrix across
heads -- so that attention weights alone can be read as feature/time
importance rather than being confounded by each head's own value
transformation [TF1].

**Why the attention claim doesn't hold (F1).** The paper isn't vague
about this -- it explicitly diagnoses *why* standard multi-head
attention isn't interpretable (different values per head mean the
attention weights alone don't tell you what mattered) and *fixes* it by
sharing values across heads. This angle's `nn.MultiheadAttention` is
exactly the un-fixed, standard case the paper is contrasting itself
against. This doesn't break the forecast -- the model still trains and
produces quantiles -- but the specific "interpretable multi-head
attention" claim in the code's own comment describes a property this
implementation doesn't have. `variable_selection_weights` remains a
real, interpretable signal regardless, since that's a separate
mechanism from attention.

**Why the strong financial result doesn't fully transfer (F2).** Unlike
several other Cluster B angles researched, TFT's paper doesn't dodge
financial data -- it specifically benchmarks against 31 stock indices'
realized volatility and wins. But "realized volatility" and "next-step
return" are different prediction targets with different statistical
properties (volatility clusters and mean-reverts; returns are close to
a random walk, per `01-arima-angle.md`'s own research). The paper's
setup also used a full year of daily context and a 5-day horizon, not
this angle's 30-bar window and 1-step horizon. The published win is
real, but for a different task shape than this angle performs.

**Why this angle still looks like the strongest of its cluster.**
Independent of the two findings above, the shared benchmark table
(already gathered for `lpatchtst`/`lstm`) shows TFT with the highest
directional accuracy of the six architectures this codebase implements
from scratch, and second-highest Sharpe. Nothing here contradicts
that -- the findings are about *why* the "interpretable" framing and the
"real financial evidence" framing are each more qualified than the code
comments suggest, not about the model underperforming.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| TF1 | Lim, Arık, Loeff & Pfister, "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting," arXiv:1912.09363 (full HTML text) | Interpretable multi-head attention design (shared value matrix across heads, explicit rationale quoted); LSTM encoder-decoder structure (historical inputs to encoder, known-future to decoder); "Volatility" benchmark dataset description (OMI realized library, 31 stock indices, daily realized volatility + returns, 252-day lookback, 5-day horizon) and TFT's P50/P90 quantile-loss results there vs. DeepAR/ConvTrans/Seq2Seq/MQRNN. | https://arxiv.org/html/1912.09363 |
| LP1 | (Already opened and cited in [12-lpatchtst-angle.md](12-lpatchtst-angle.md)) Saly-Kaufmann, Wood, Peter-Calliess & Zohren, "Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance," arXiv:2603.01820, 2026 | Reused Table 2 entry for TFT (Sharpe 2.20, hit rate 58.4%) within the same six-architecture comparison already used for `lpatchtst`/`lstm`. | https://arxiv.org/html/2603.01820 |
