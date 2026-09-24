# 15 — moment

- **Angle id:** `moment`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/moment/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

**`model_backend` is always `"fallback_proxy"` for this angle.** The
real MOMENT package (`momentfm`) failed to install here -- a genuine
Python 3.12 incompatibility, not a network issue. What runs instead is a
geometric random walk with drift (from the last 20 returns) and an 80%
band. MOMENT is normally multi-task (forecasting, classification,
anomaly detection, imputation); only the forecasting piece is even
attempted here, and it isn't the real model.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | *(Real MOMENT)* Splitting a series into fixed-length **patches**, masking some at random, and training the model to reconstruct them teaches useful general-purpose time-series representations. | [MT1] |
| A2 | *(Real MOMENT)* These representations transfer to forecasting, classification, anomaly detection, and imputation -- one pretrained backbone, several downstream tasks. | [MT1] |
| A3 | *(Real MOMENT's own strong forecasting results)* Best long-horizon results come from **linear probing** -- training a small linear head on top of the frozen pretrained embeddings -- not from the frozen model used with no adaptation at all. | [MT1] |
| A4 | *(This angle's actual fallback)* The next several closes follow a **geometric random walk with drift**, where drift is the mean of the last 20 realized returns and the band widens with √(horizon) from the full-history residual std. | code's own design |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Linear-probed MOMENT vs. other forecasting models, long-horizon benchmark datasets | "Near state-of-the-art performance on most datasets and horizons, and is only second to PatchTST which generally achieves the lowest MSE." Beats LLM-repurposed forecasters (TimeLLM, GPT4TS) on many datasets/horizons. | [MT1] |
| R2 | Evaluation datasets used for the long-horizon forecasting benchmark | Includes the Informer benchmark suite's **Exchange-Rate** dataset -- the same dataset already researched for `dlinear` and `itransformer` in this folder. | [MT1] |
| R3 | Python 3.12's removal of `pkgutil.ImpImporter`/`ImpLoader` | Officially removed as part of the same Python 3.12 cleanup that removed `distutils`. Independently reported in pybind11's own build with the **identical** error string this codebase's install attempt hit (`AttributeError: module 'pkgutil' has no attribute 'ImpImporter'`), traced to `pkg_resources` still calling `register_finder(pkgutil.ImpImporter, find_on_path)` against a since-removed CPython interface (CPython issue #98573). | [MT2], [MT3] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `pip install momentfm` fails with `AttributeError: module 'pkgutil' has no attribute 'ImpImporter'`, confirmed via a real install attempt and diagnosed as a Python-3.12-vs-old-transitive-dependency incompatibility. | This is a real, documented Python 3.12 breaking change -- `pkgutil.ImpImporter` removal traces to CPython issue #98573; a real-world pybind11 build hit the **identical** error string, caused by `pkg_resources` (an old `setuptools` component) still referencing the removed class [MT3]. | **Correctly diagnosed, and independently corroborated character-for-character.** This isn't a misattributed or guessed cause -- it's a known, specific, well-documented incompatibility class, and the code's fallback decision follows directly from it. |
| F2 | If it *had* installed, `compute()` would call the pretrained model directly, with **no fine-tuning or linear-probing step** -- a true zero-shot/frozen-embedding use. | MOMENT's own strongest reported forecasting results specifically come from **linear probing**, not the frozen model alone [MT1]. | **Worth noting even though the real model never runs here**: had the install succeeded, the "near state-of-the-art" headline result wouldn't have transferred automatically -- this angle's per-symbol, per-request call pattern has no natural place to fit a linear-probing step (fine-tuning a head per ticker per run), so even a working `momentfm` install would likely have underperformed the paper's own best-reported numbers. This mirrors the same zero-shot-vs-adapted gap already found for `chronos` (R1 in [03-chronos-angle.md](03-chronos-angle.md)). |
| F3 | Fallback's `point` and `spread` both scale from the **same fixed variable** (`last = float(closes[-1])`), with `point = last * (1 + drift) ** steps` computed analytically rather than via a step-by-step loop. | -- (internal consistency check, code-only) | **No bug here** -- unlike `lag_llama` and `moirai`'s fallbacks (both flagged for anchoring the spread to a stale price while the point forecast compounded via a loop), this fallback's closed-form exponentiation keeps both quantities consistently anchored to the same starting price. Worth noting as a contrast: three angles share a near-identical "drift + Gaussian band" fallback shape, and only this one avoids the anchoring bug the other two have. |
| F4 | `drift` is computed from the **last 20** returns; `resid_std` (used to build the band) is computed from **the entire returns history**. | -- (internal inconsistency, code-only) | **Minor inconsistency**: if the ticker's volatility regime shifted meaningfully within the observed history, the band width reflects a different (longer, possibly stale) window than the drift estimate does. Not necessarily wrong, but the two window choices aren't matched, and nothing documents why. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | Always `"fallback_proxy"` -- the real MOMENT never runs here. |
| `fallback_reason` | The exact `pkgutil.ImpImporter` install failure and Python 3.12 diagnosis. |
| `task` | Always `"forecasting"`. |
| `task_note` | Explicit reminder that MOMENT's other tasks (embeddings, anomaly detection, imputation) aren't implemented at all, not just proxied. |
| `forecast_horizon` | Always `5` (bars ahead). |
| `last_close` | Last actual close the fit saw. |
| `point_forecast` | List of 5 geometrically-compounding drift-based price forecasts. |
| `p10_forecast` / `p90_forecast` | 10th/90th percentile Gaussian band, consistently anchored (see F3). |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fallback fit produced a forecast. | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) closes. | + `n_observations`. |

No `fit_failed` status -- same reasoning as `lag_llama`/`moirai`: a
closed-form drift/std computation has no realistic failure mode.

## 7. Comprehensive explanation  *(for humans only)*

**What MOMENT is.** A patch-based transformer, similar in spirit to
PatchTST's patching idea, but pretrained with **masked reconstruction**
(like a masked autoencoder for images, applied to time series): patches
are randomly masked during pretraining and the model learns to
reconstruct them, producing embeddings meant to be reusable across five
different downstream tasks -- forecasting (long and short horizon),
classification, anomaly detection, and imputation -- rather than
training a separate model per task [MT1]. Its best reported forecasting
results come from linear probing on top of those frozen embeddings, and
it's reported competitive with, just behind, PatchTST specifically, and
ahead of LLM-repurposed forecasters like TimeLLM and GPT4TS [MT1].

**Why the install genuinely failed, not just "wasn't tried hard
enough."** `pkgutil.ImpImporter` is a real casualty of Python's own
`imp`-to-`importlib` migration: deprecated in Python 3.4, it was finally
removed in 3.12. Any package whose build tooling still references it
(usually via an old, un-upgraded `setuptools`/`numpy.distutils`
dependency somewhere in its transitive chain) breaks outright on 3.12 --
this exact failure signature shows up independently across several
unrelated projects' own bug trackers, not just this one attempt. The
code's diagnosis matches a documented, systemic incompatibility class,
not a one-off fluke.

**What "near state-of-the-art" would have actually required (F2).**
Even setting the install failure aside, MOMENT's headline forecasting
result isn't "load the pretrained model and forecast" -- it's "load the
pretrained model, then train a small linear head per dataset via
probing." This angle's calling pattern (one `compute()` call per symbol
per request, no separate training phase) has no natural place for that
step. So a hypothetical working install would likely have run MOMENT
closer to zero-shot than to the setting its best-known numbers come
from -- the same gap already documented for `chronos`'s zero-shot
financial performance being much weaker than its general-benchmark
numbers.

**Comparing the three "simple fallback" angles (F3).** `lag_llama`,
`moirai`, and `moment` all fall back to a similar shape: a point
forecast plus a Gaussian quantile band built from a residual spread.
Tracing all three side by side surfaced a real difference: `moment`'s
closed-form exponential compounding keeps the point forecast and the
band's price-anchor consistent, while the other two's step-by-step
loops let the point forecast advance while the band's anchor stayed
fixed at the original price -- the bug documented in
[11-lag_llama-angle.md](11-lag_llama-angle.md) and
[14-moirai-angle.md](14-moirai-angle.md).

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| MT1 | Goswami, Szafer, Choudhry, Cai, Li & Dubrawski, "MOMENT: A Family of Open Time-series Foundation Models," arXiv:2402.03885, ICML 2024 (full HTML text) | List of five supported tasks; patch-based masked-reconstruction architecture description; linear-probing being the source of the "near state-of-the-art" forecasting result, second only to PatchTST; outperforming TimeLLM/GPT4TS; Exchange-Rate dataset in the long-horizon evaluation benchmark. | https://arxiv.org/html/2402.03885 |
| MT2 | Python 3.12 "What's New" official documentation, "Important deprecations, removals or restrictions" section | Confirmed `distutils` removal (PEP 632) as part of the same Python 3.12 cleanup wave; virtual environments no longer pre-install `setuptools`/`distutils`/`pkg_resources` by default. | https://docs.python.org/3/whatsnew/3.12.html |
| MT3 | GitHub issue, `pybind/pybind11#4646`, "[BUG]: Python 3.12 will remove deprecated ImpImporter from pgkutil" | Independent confirmation, with the **identical** `AttributeError` string this codebase's own install attempt hit; root cause traced to `pkg_resources` calling `register_finder(pkgutil.ImpImporter, find_on_path)` against the now-removed CPython interface (CPython issue #98573). | https://github.com/pybind/pybind11/issues/4646 |
