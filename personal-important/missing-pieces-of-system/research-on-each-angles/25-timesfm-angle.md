# 25 — timesfm

- **Angle id:** `timesfm`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timesfm/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Zero-shot forecast from Google's TimesFM 2.5 (200M params), a
general-purpose (not finance-specific) foundation model -- a comparison
baseline like `chronos`, not a first-choice signal. Reports a point
forecast plus all 9 of the model's own genuinely trained decile
outputs (q10-q90) -- unlike `timer_timerxl`'s post-hoc statistical band,
these deciles are real model output. **Every technical claim checked
against the model's real documentation came back exactly verified** --
see F1-F3.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | A `max_context` of 1024 is the model's own documented default/recommended operating configuration, not an arbitrary choice. | [TS1] |
| A2 | The model's `forecast()` quantile output is ordered `[mean, q10, q20, ..., q90]` along its last axis -- index 0 is the mean, indices 1-9 are the 9 real decile levels. | [TS1] |
| A3 | TimesFM's pretraining corpus is general-purpose (web traffic, search trends, synthetic data), with no financial data -- consistent with treating it as a comparison baseline, not a finance-specific signal. | [TS1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | `google/timesfm-2.5-200m-pytorch` model card's own documented `ForecastConfig` example | `max_context=1024, max_horizon=256, normalize_inputs=True, use_continuous_quantile_head=True, force_flip_invariance=True, infer_is_positive=True, fix_quantile_crossing=True` -- given as the model's own recommended configuration, character-for-character. | [TS1] |
| R2 | Quantile output shape and ordering | "Mean, then 10th to 90th quantiles" -- shape `(2, 12, 10)` in the card's own worked example: index 0 of the last axis is the mean, indices 1-9 are q10 through q90 in order. | [TS1] |
| R3 | Pretraining corpus composition | "GiftEvalPretrain, Wikimedia Pageviews, Google Trends top queries," plus synthetic data -- no financial datasets listed anywhere in the model card. | [TS1] |
| R4 | Version 2.5 vs. earlier TimesFM checkpoints | "We changed the structure of the model to fuse QKV matrices into one for speed optimization... Results should be unchanged" -- a performance/engineering change, not an accuracy-affecting one. | [TS1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `MAX_CONTEXT = 1024` (raised from an earlier `256`, per the code comment, specifically to match "the model's own documented default operating configuration"). | The checkpoint's own model card gives `max_context=1024` in its own example `ForecastConfig` [TS1]. | **Confirmed correct, exact match.** |
| F2 | `_get_model` calls `timesfm.ForecastConfig(max_context=MAX_CONTEXT, max_horizon=HORIZON, normalize_inputs=True, use_continuous_quantile_head=True, force_flip_invariance=True, infer_is_positive=True, fix_quantile_crossing=True)`. | The model card's own example `ForecastConfig` uses the identical parameter names and identical values for every field except `max_horizon` (its example uses 256, the max; this angle correctly overrides it to `HORIZON=5` for its own 5-step forecast need) [TS1]. | **Confirmed correct** -- this isn't guessed-at configuration; it's copied faithfully from the model's own documented usage example, with only the one parameter changed that legitimately needs to differ for this angle's shorter horizon. |
| F3 | `quantile_fc[0, :, i + 1]` extracts deciles, explicitly commented "index 0 is the mean, indices 1-9 are the 9 real decile levels," with a fixed-earlier note that a prior version discarded 7 of the 10 real quantile levels and kept only q10/q90. | The model card's own worked example states exactly this ordering: "mean, then 10th to 90th quantiles" [TS1]. | **Confirmed correct indexing**, and the referenced prior fix (keeping all 9 deciles instead of discarding 7) is a real, verifiable improvement in information retained per call. |
| F4 | Docstring states the `timesfm[torch]` backend "needs no jax/flax, so this does not touch the already-installed torch 2.13 build." | -- (an environment-compatibility claim, not independently re-verified here) | Consistent with the general pattern already seen in `kronos`/`moment`, where dependency conflicts were the deciding factor for whether a real model could be installed -- here the outcome (real weights, actually used) is the positive case of that same due-diligence. |
| F5 | Fallback (linear-trend extrapolation + residual-normal quantiles across all 9 decile levels) only fires if the real checkpoint can't load, clearly labeled via `model_backend`/`fallback_reason`. | -- | Same honest-labeling posture as every other fallback-capable angle researched in this folder. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | `"pretrained"` = real TimesFM ran. `"fallback_proxy"` = linear-trend fallback ran instead. **Check this first.** |
| `checkpoint` | `"google/timesfm-2.5-200m-pytorch"` when pretrained; `null` on fallback. |
| `fallback_reason` | Why the fallback fired; `null` when the real model ran. |
| `context_length_used` | How many bars were actually fed (capped at `MAX_CONTEXT=1024`). |
| `forecast_horizon` | Always `5`. |
| `last_close` | Last actual close the model saw. |
| `point_forecast` | 5-step price forecast. |
| `decile_forecasts` | Dict `q10`...`q90`, each a 5-element list -- **on the pretrained path, these are the model's own genuinely trained quantile-head output**, not a statistical construction (contrast `timer_timerxl`); on the fallback path, they're a Gaussian approximation shaped to match the same output structure. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | A forecast was produced -- by the real model or the fallback; see `model_backend`. | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) closes. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What TimesFM is.** A decoder-only transformer pretrained zero-shot
across a large, general (not domain-specific) time-series corpus --
web traffic, search trends, synthetic series -- with no financial data
in the mix [TS1]. Version 2.5 is a structural (QKV-fusion) speed
optimization over earlier checkpoints, explicitly not an accuracy
change [TS1]. Like `chronos`, it's positioned here as a general-purpose
comparison baseline, not a signal expected to be finance-aware out of
the box.

**Why every check here came back clean.** Three separate, independently
checkable claims -- the recommended context length, the exact
`ForecastConfig` parameter set, and the quantile output's index
ordering -- were each verified word-for-word against the model's own
Hugging Face card rather than assumed from general familiarity with the
architecture. All three matched exactly, including a parameter set
copied faithfully enough to be a near-literal transcription of the
card's own example. Combined with the already-fixed "kept all 9 deciles
instead of discarding 7" improvement documented in the code's own
comments, this angle -- like `timer_timerxl` researched immediately
before it -- shows that this research folder's job isn't only to find
bugs: confirming an implementation is faithful to its source, with the
same rigor used to find the bugs in other angles, is an equally real
result.

**Contrast with `timer_timerxl`, cross-referenced from the glossary.**
The glossary itself already draws the right distinction: this angle's
deciles are the model's genuine trained uncertainty; `timer_timerxl`'s
p10/p90 is explicitly a post-hoc statistical band bolted onto a
deterministic point forecaster. That's a real, useful difference for a
downstream reader deciding how much to trust either angle's stated
uncertainty, and it's accurately represented in both angles' own
metadata.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| TS1 | Hugging Face model card, `google/timesfm-2.5-200m-pytorch` | Recommended `max_context=1024`; full `ForecastConfig` example (all 7 parameters, values matched against this angle's own call); quantile output shape and ordering ("mean, then 10th to 90th quantiles," shape `(2, 12, 10)`); pretraining corpus composition (GiftEvalPretrain, Wikimedia Pageviews, Google Trends, synthetic -- no financial data); version 2.5's QKV-fusion change described as a speed optimization with unchanged results. | https://huggingface.co/google/timesfm-2.5-200m-pytorch |
