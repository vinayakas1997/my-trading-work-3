# 13 — lstm

- **Angle id:** `lstm`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lstm/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A small, single-layer LSTM (16 hidden units) trained from scratch on
this ticker every run, processing the close-price window one step at a
time and carrying a learned memory forward. One-step point forecast,
thresholded to a direction. The glossary frames it as "a competent
generalist forecaster, not the strongest or weakest of its cluster."

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Gated memory cells with **multiplicative gates** let error signals flow backward through time without vanishing or exploding, unlike a plain recurrent net. | [LS1] |
| A2 | *(Code's own docstring)* "Lightweight LSTM/GRU/Mamba often beat huge transformers on financial data." | referenced design note; directly corroborated by [LP1] (see R2) |
| A3 | Staying genuinely small (single layer, 16 units, well under 50K parameters) is deliberate, not a placeholder. | code's own docstring |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Original 1997 comparisons vs. BPTT, RTRL, Recurrent Cascade-Correlation, Elman nets, Neural Sequence Chunking, on long-time-lag artificial tasks | LSTM "leads to many more successful runs, and learns much faster," and solves long-time-lag tasks "that have never been solved by previous recurrent network algorithms." | [LS1] |
| R2 | Same daily-futures benchmark already used for `lpatchtst` -- Sharpe ratio and hit rate by architecture | Plain LSTM: **Sharpe 1.32, hit rate 55.4%** -- beats PatchTST (0.86, 54.1%) and iTransformer (0.35, 52.9%) outright, though it trails TFT (2.20, 58.4%) and the LSTM+PatchTST hybrid (2.32, 57.7%). | [LP1] (already opened for [12-lpatchtst-angle.md](12-lpatchtst-angle.md)) |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Module docstring cites "the reported ~51% directional-accuracy figure" for this angle's design target. | The benchmark paper this codebase cites for the closely related `lpatchtst` angle (same "six trained-from-scratch architectures... source survey" phrasing in both spec.yaml files) reports plain LSTM at **55.4%** hit rate, not ~51% [LP1, R2]. | **Possible stale/mismatched figure, flagged with appropriate uncertainty.** It's not certain the ~51% figure and the `lpatchtst`/[LP1] figure trace back to the same source document -- the code doesn't cite an arXiv ID for this specific number the way `lpatchtst`'s spec does. But given the two spec files' nearly identical framing of "the six trained-from-scratch architectures the source survey found," if they are the same survey, this angle's own docstring understates its cited benchmark's actual number by about 4-5 points. Worth checking directly against `19-lstm.md` if that design doc still exists somewhere, since it isn't present in this checked-out repo. |
| F2 | Uses `torch.nn.LSTM` -- the standard modern implementation with **three** gates (input, forget, output). | Hochreiter & Schmidhuber's original 1997 LSTM had **no forget gate** -- only input and output gates; the forget gate was added later (Gers et al., not independently verified here). | Not a bug -- PyTorch's `nn.LSTM` is the now-standard formulation almost universally meant by "LSTM" today, and the code's citation to "gated memory cells" is accurate to that. Noted only for precision: the exact architecture in code postdates, and differs from, the originally cited mechanism. |
| F3 | Kept genuinely small: 1 layer, 16 hidden units -- roughly 1,150 LSTM parameters plus a 17-parameter linear head, both well under the docstring's stated "well under 50k params" claim. | -- (arithmetic check, not a literature question) | **Confirmed accurate** by direct parameter-count arithmetic: `4 * hidden * (input + hidden + 1)` for the LSTM plus `hidden + 1` for the head ≈ 1,169 total. |
| F4 | Same benchmark data source as `lpatchtst`: daily futures across 5 asset classes, 2010-2025 -- this angle runs on 1min-1D individual equities. | -- | Same domain-transfer caveat already documented in [12-lpatchtst-angle.md](12-lpatchtst-angle.md) -- not repeated in full here. |
| F5 | No direction-hit naive baseline (RMSE/MAE only), same DLinear-family pattern. | Consistent with the same reasoning already established for `dlinear`/`itransformer`/`lpatchtst`. | No new finding -- consistent design choice across the whole point-forecast family. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_price` | One-step-ahead predicted close. |
| `forecast_return` | `(forecast_price - last_close) / last_close`. |
| `direction` | `up`/`down`/`flat`, thresholded at ±0.01%. |
| `last_close` | Last actual close the model saw. |
| `lookback` | Always `30`. |
| `hidden_size` | Always `16`. |
| `n_train_windows` | How many 30-bar training examples it learned from. |
| `train_loss` | Final training MSE -- fit quality, not forecast accuracy. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_BARS` (100) bars, **or** fewer than 20 training windows -- both reasons share this one status (same pattern as `dlinear`/`itransformer`/`lpatchtst`). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What LSTM solves, and why it still matters here.** Plain recurrent
networks struggle to learn from events far in the past because
backpropagated error either explodes or decays exponentially with each
step it travels backward [LS1]. LSTM's fix is a memory cell whose
internal state is protected by multiplicative gates, so the network can
learn *when* to let new information in and *when* to let error flow
back through the cell largely unchanged -- Hochreiter & Schmidhuber call
this a "constant error carousel" [LS1]. That's a 1997-era mechanism, but
the specific claim behind putting it in this system -- that lightweight
recurrent models can hold their own against much larger transformer
architectures on financial data -- gets direct, current support from the
same benchmark paper already used for `lpatchtst`: plain LSTM
(1.32 Sharpe) beats both PatchTST (0.86) and iTransformer (0.35) on the
same daily-futures test, even though it's a fraction of their
complexity [LP1].

**Where this angle sits among its cluster.** Cross-referencing the full
table already gathered for `lpatchtst`: DLinear 0.77, iTransformer 0.35,
PatchTST 0.86, LSTM 1.32, TFT 2.20, LSTM+PatchTST 2.32 (Sharpe). LSTM is
solidly mid-pack -- better than the two pure-transformer entries, worse
than the two later, more elaborate hybrids -- which lines up with the
glossary's own framing as "a competent generalist forecaster, not the
strongest or weakest."

**The ~51% figure (F1).** This is the one open question from this
research pass, not a confirmed error: the code's own comment attributes
"~51% directional accuracy" to a design note this repo no longer
contains (`19-lstm.md`). If that note draws on the same survey cited for
`lpatchtst`, the real number for plain LSTM in that survey is 55.4%, not
~51%. Without the original note available to check directly, this is
flagged as a discrepancy worth resolving, not asserted as a confirmed
citation error.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| LS1 | Hochreiter & Schmidhuber, "Long Short-Term Memory," *Neural Computation* 9(8):1735-1780, 1997 (author's own PDF, pp. 1-3) | Core problem (vanishing/exploding backpropagated error over long time lags); LSTM's fix (constant error carousel, multiplicative gate units); reported outperformance over BPTT/RTRL/Recurrent Cascade-Correlation/Elman nets/Neural Sequence Chunking on long-lag tasks. | https://www.bioinf.jku.at/publications/older/2604.pdf |
| LP1 | (Already opened and cited in [12-lpatchtst-angle.md](12-lpatchtst-angle.md)) Saly-Kaufmann, Wood, Peter-Calliess & Zohren, "Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance," arXiv:2603.01820, 2026 | Reused Table 2 entry for plain LSTM (Sharpe 1.32, hit rate 55.4%) and the full cross-architecture comparison, to place this angle among the same cluster already researched for `lpatchtst`. | https://arxiv.org/html/2603.01820 |
