# 12 — lpatchtst

- **Angle id:** `lpatchtst`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`); patch
  branch shared from `angles/patchtst/_patch_transformer.py`
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A small model trained from scratch on this ticker, combining an LSTM
branch and a patch-transformer branch (shared code with `patchtst`) that
both read the same closing-price window, concatenate their outputs, and
feed one linear head for the next-bar forecast. The glossary calls this
"the single best-performing trained-from-scratch model in this system's
own benchmark survey" -- **that claim needs a metric qualifier**, and the
architecture itself differs from the cited paper's actual design (see
F1).

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | *(Code's own design)* An LSTM branch and a patch-transformer branch, run in **parallel** on the same raw window and concatenated, combine sequential-dependency modeling with patch-based regularization. | code's own docstring |
| A2 | *(Cited paper's real architecture)* An LSTM run as a **channel-wise temporal denoiser first**, whose denoised output is then fed **into** PatchTST -- a sequential composition, not two parallel branches. | [LP1] |
| A3 | *(Cited paper)* Testing across daily futures data spanning bonds, commodities, energy, FX and equity indices (2010-2025) is representative enough to rank architectures by risk-adjusted performance. | [LP1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Full results table, daily futures, 2010-2025, Sharpe ratio | DLinear 0.77, PatchTST 0.86, iTransformer 0.35, LSTM 1.32, **LSTM+PatchTST 2.32**, TFT 2.20, VSN+LSTM (best overall) 2.39. | [LP1] |
| R2 | Same table, directional accuracy (hit rate) | DLinear 53.9%, PatchTST 54.1%, iTransformer 52.9%, LSTM 55.4%, **LSTM+PatchTST 57.7%**, **TFT 58.4%**, VSN+LSTM 58.8%. | [LP1] |
| R3 | Paper's own stated takeaway | "Models explicitly designed to learn rich temporal representations consistently outperform linear benchmarks and generic deep learning models" -- VSN+LSTM the single best overall. | [LP1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | LSTM branch and patch branch both process the **same raw window independently and in parallel**; their final representations are concatenated before one linear head. | The paper's actual "LSTM+PatchTST" is **sequential**: "An LSTM as a channel-wise temporal denoiser prior to PatchTST. The LSTM stabilizes per-channel representations, while PatchTST aggregates medium- and long-range dependencies across denoised temporal patches" [LP1]. | **Real architecture-fidelity gap.** The code's design (parallel branches, concatenate, linear head) is a different, simpler composition than what the benchmark paper actually tested. The 57.7%/2.32 numbers cited as this angle's expected performance come from an architecture this code doesn't structurally replicate -- the LSTM here never denoises anything the patch branch sees; both see the raw window. |
| F2 | Glossary/spec both frame `lpatchtst` as "the single best-performing trained-from-scratch model," unqualified. | Among the 6 architectures this codebase also implements as separate angles (`dlinear`, `lstm`, `patchtst`, `itransformer`, `tft`, and this hybrid), LSTM+PatchTST does have the **highest Sharpe** (2.32) -- but **not** the highest directional accuracy: `tft` reports 58.4% vs. this angle's 57.7% [LP1, R2]. | **"Best-performing" needs a metric.** True for Sharpe among these six, false for hit rate specifically -- `tft` (not yet researched in this folder) reportedly beats it there. A reader relying on "best-performing" for a directional read specifically would be picking the wrong angle. |
| F3 | Reported benchmark data: **daily** futures bars across bonds/commodities/energy/FX/equity indices, 2010-2025 [LP1]. This angle runs on **1min through 1D** individual equity bars. | -- | Same domain-transfer caveat already flagged for other benchmark-cited angles in this folder: the cited numbers come from a different asset class (futures, not equities), a different frequency (daily only, vs. this angle's intraday timeframes too), and a fixed historical window -- not validated on what this angle is actually run against. |
| F4 | Uses the same `PatchEncoderBranch` as the standalone `patchtst` angle (shared code, `patch_len=8`, `stride=4`, `d_model=16`). | -- | Sensible reuse, avoids duplicating the patch-embedding logic -- a design positive, not a finding. |
| F5 | No `naive_baseline` direction-hit comparison -- RMSE/MAE only, same reasoning as `dlinear` (a flat "no change" forecast is always "flat," so hit-rate against it isn't meaningful). | Consistent with `04-dlinear-angle.md`'s F4 finding that this exact naive-baseline gap mattered most for `dlinear`. | Here it matters less: this angle's whole premise leans on the *cited* benchmark's directional-accuracy number, but that number belongs to a different (sequential) architecture on a different dataset -- so the in-repo naive baseline (even an RMSE-only one) would still be useful evidence this angle currently doesn't compute. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_price` | One-step-ahead predicted close. |
| `forecast_return` | `(forecast_price - last_close) / last_close`. |
| `direction` | `up`/`down`/`flat` from `forecast_return` (via the shared `direction()` helper). |
| `last_close` | Last actual close the model saw. |
| `lookback` | Always `32`. |
| `lstm_hidden_size` | Always `16`. |
| `n_patches` | Number of patches the patch branch split the window into. |
| `n_train_windows` | How many 32-bar training examples it learned from. |
| `train_loss` | Final training MSE -- fit quality, not forecast accuracy. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_BARS` (100) bars, **or** fewer than 20 training windows -- both reasons share this one status (same pattern as `dlinear`/`itransformer`). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What the cited paper actually tested.** A 2026 large-scale benchmark
of deep learning architectures on 15 years of daily futures data across
five asset classes, comparing linear models, recurrent networks,
transformers, state-space models and hybrids by Sharpe ratio,
directional accuracy, Calmar ratio and other risk-adjusted metrics
[LP1]. Its "LSTM+PatchTST" entry -- the one this angle's name and
performance numbers are drawn from -- is specifically a **sequential**
hybrid: the LSTM's job is to denoise each channel's representation
before PatchTST ever sees it, not to run alongside PatchTST as an
independent second opinion.

**What this angle actually builds (F1).** Both branches read the exact
same raw (z-scored) window. The LSTM's final hidden state and the patch
branch's encoding are computed independently, then concatenated and
passed through one shared linear layer. This is a legitimate,
simpler design -- late fusion of two different views of the same
data -- but it is not the paper's "LSTM-as-denoiser-then-PatchTST"
design. Whether late-fusion parallel branches perform anywhere near the
paper's reported 57.7% hit rate / 2.32 Sharpe for the *sequential*
version is an open, untested question -- the two are different models
that happen to share the same two building blocks and the same name.

**The "best of six" framing (F2/F3).** Restricting to just the
architectures this codebase separately implements as angles, this one
does hold the best Sharpe ratio in the cited table. But "best-performing"
in the glossary reads as a general endorsement, and on the *other*
headline metric in the same table (directional accuracy), `tft`
reportedly scores higher (58.4% vs. 57.7%). Both numbers come from a
daily-futures benchmark, not this codebase's actual equity/intraday use
case, so neither ranking is validated against what this angle is run
against in production -- the "best of six" claim is best read as "best
Sharpe, on a different market, in a different architecture than what's
implemented," not as a guarantee about this angle's own output.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| LP1 | Saly-Kaufmann, Wood, Peter-Calliess & Zohren, "Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance," arXiv:2603.01820, 2026 (full HTML text) | Full Table 2 results (Sharpe ratio and hit rate for DLinear, LSTM, PatchTST, iTransformer, TFT, LSTM+PatchTST, VSN+LSTM); architecture descriptions of LSTM+PatchTST (sequential, LSTM-as-denoiser) and VSN+LSTM; dataset details (daily futures, 5 asset classes, 2010-2025); stated overall-best-performer conclusion (VSN+LSTM). | https://arxiv.org/abs/2603.01820 , https://arxiv.org/html/2603.01820 |
