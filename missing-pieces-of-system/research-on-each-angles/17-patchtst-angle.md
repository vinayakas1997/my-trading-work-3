# 17 — patchtst

- **Angle id:** `patchtst`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`); patch
  encoder shared with `lpatchtst` via `_patch_transformer.py`
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A small transformer trained from scratch on this ticker every run,
splitting the close-price window into overlapping patches (like image
patches) and running self-attention across them. Glossary already flags
that this shares its core with `lpatchtst`, so the two "aren't fully
independent signals." **The architecture's own authors deliberately
excluded financial exchange-rate data from their benchmark**, citing
market efficiency (see F1) -- worth knowing before treating this as a
validated-on-finance model.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Splitting the lookback window into fixed-length **patches** (rather than one token per timestep) retains local structure and cuts attention's compute/memory cost quadratically for the same window length. | [P1] |
| A2 | **Channel independence**: every channel is processed by the *same shared weights*, applied separately -- not mixed together the way `itransformer` mixes channels. | [P1] |
| A3 | A **learned** (not fixed/sinusoidal) additive position encoding is enough to let the model track patch order. | [P1] |
| A4 | *(The paper's own stated reason for excluding financial data)* Under an efficient market, "the best prediction for x_t will be just x_{t-1}" -- so a naive forecast can match or beat sophisticated models on this kind of data, making it a poor benchmark for judging architecture quality. | [P1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Exchange-Rate dataset, decision to include/exclude from the paper's own benchmark | **Deliberately excluded.** The paper states: "Financial datasets generally have different properties compared to time series datasets in other fields, for example the predictability. It is well known that if a market is efficient, the best prediction for x_t will be just x_{t-1}." A naive baseline matching or beating sophisticated models on this dataset is given as supporting evidence for the exclusion. | [P1] |
| R2 | Patch length/stride ablation | `P=16, S=8` used for the main model; ablation found "P between {8,16} seems to be general good numbers." | [P1] |
| R3 | Positional encoding choice | "A learnable additive position encoding... is applied to monitor the temporal order of patches" -- not fixed/sinusoidal. | [P1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Runs PatchTST's core architecture directly on this ticker's own close-price series -- exactly the kind of data (individual equity prices) the paper's own authors chose to keep *out* of their benchmark. | The paper explicitly excludes financial/exchange-rate data from its results, citing the efficient market hypothesis and naive-baseline competitiveness as the reason [P1]. | **The strongest version of a pattern already seen across this cluster** (`dlinear`, `itransformer`, `moment` all only report weak or absent results on the one financial-ish dataset their papers touch). Here it goes one step further: PatchTST's own creators didn't just report a weak financial result -- they decided financial data wasn't a fair or informative benchmark for their architecture *at all*, and said so directly. Using it here isn't wrong, but there is genuinely no published evidence, from the paper itself, that PatchTST is good at this exact kind of data -- the authors' own skepticism, not just an absent data point. |
| F2 | `PATCH_LEN=8, STRIDE=4`. | Main experiments used `P=16, S=8`; ablation found `P in {8, 16}` both "general good numbers" [P1]. | Reasonable -- `patch_len=8` sits inside the paper's own validated-good range, though the exact main-model setting (16/8) isn't what's used here. Not a clear deviation, just a smaller/denser variant. |
| F3 | Learned positional encoding (`nn.Parameter(torch.zeros(1, n_patches, d_model))`, trained alongside everything else). | Matches the paper's own choice: a learnable additive position encoding, not fixed/sinusoidal [P1]. | **Correct**, verified against the paper's own description. |
| F4 | Channel independence is implemented (each channel would get its own forecast via shared weights), but `compute()` only ever passes the single `close` channel. | Channel independence's whole point is applying one shared model across *several* channels without mixing them [P1]. | With one channel, channel-independence is trivially satisfied but doesn't demonstrate anything -- there's nothing to *not* mix. The spec.yaml is upfront about this ("additional channels would each get their own independent forecast... out of scope for the single-series bars this angle receives"), so this isn't a hidden gap, just a design constraint worth restating plainly. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_price` | One-step-ahead predicted close. |
| `forecast_return` | `(forecast_price - last_close) / last_close`. |
| `direction` | `up`/`down`/`flat`, thresholded at ±0.01%. |
| `last_close` | Last actual close the model saw. |
| `lookback` | Always `32`. |
| `patch_len` | Always `8`. |
| `n_patches` | Number of patches the window was split into (7, per the module's own comment). |
| `n_train_windows` | How many 32-bar training examples it learned from. |
| `train_loss` | Final training MSE -- fit quality, not forecast accuracy. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_BARS` (100) bars, **or** fewer than 20 training windows -- both reasons share this one status (same pattern as `dlinear`/`itransformer`/`lpatchtst`/`lstm`). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What PatchTST's real contribution is.** Instead of feeding a
transformer one token per timestep (expensive, and each token carries
almost no information on its own), split the series into overlapping
sub-sequences ("patches"), embed each patch as one token, and run
attention across those -- fewer, richer tokens, quadratically cheaper
attention for the same lookback, and each channel processed
independently by shared weights rather than mixed together [P1]. It's
the same patching idea `dlinear`'s trend/seasonal split doesn't use but
`itransformer`'s variate-tokens conceptually rhyme with (patches over
time vs. tokens over variates).

**The exclusion that matters most here (F1).** Unlike `dlinear` or
`itransformer`, whose papers at least *report* a (weak) result on
Exchange-Rate, PatchTST's authors looked at that same dataset and
decided not to include it in their results at all -- specifically
because, under an efficient market, the best forecast is often just
"yesterday's price," and a naive baseline matching sophisticated models
under those conditions makes the benchmark uninformative for judging
architecture quality [P1]. That's the same random-walk theme this whole
research folder keeps surfacing (`01-arima-angle.md`'s core finding), but
here it comes from the architecture's own authors choosing not to test
their own model on it, rather than from a weak reported number.

**What this means for this angle specifically.** Nothing about this
finding says PatchTST *can't* work on stock prices -- only that there is
no published evidence, positive or negative, from the paper itself. The
in-repo `naive_baseline.py` (RMSE/MAE comparison) is the only actual
evidence this codebase has about whether this particular
implementation, on this particular data, beats doing nothing -- exactly
the kind of check the paper's own reasoning says matters most for this
type of data.

**Implementation fidelity.** Setting the financial-applicability
question aside, the mechanism itself matches the paper closely: patch
length in the paper's own validated-good range, a learned (not
sinusoidal) positional encoding exactly as described, and genuine
channel-independent design even though only one channel is ever
exercised here.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| P1 | Nie, Nguyen, Sinthong & Kalagnanam, "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers" (PatchTST), arXiv:2211.14730, ICLR 2023 (full HTML text, incl. Appendix A.1.1) | Patching + channel-independence design and stated benefits (local semantic retention, quadratic compute/memory reduction); learned (not fixed) positional encoding; patch length/stride ablation (`P=16,S=8` main setting, `P in {8,16}` both "good"); explicit exclusion of the Exchange-Rate dataset from the benchmark, with the efficient-market-hypothesis rationale and naive-baseline-competitiveness justification quoted directly. | https://arxiv.org/html/2211.14730 |
