# 24 — timer_timerxl

- **Angle id:** `timer_timerxl`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Patch-based (96-point patches) autoregressive transformer, real
pretrained weights (`thuml/timer-base-84m`, 84M params). **The name says
"Timer / Timer-XL," but the actual downloaded checkpoint is base
Timer, not Timer-XL** -- disclosed honestly in the code's own docstring.
Two numbers in that docstring that looked, at first glance, like they
might not match the real published sources (260B pretraining points,
2880-point max context) were both directly verified against the
checkpoint's own model card and turned out to be **correct** -- see F1/F2.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Splitting the series into fixed 96-point patches and autoregressively predicting the next patch, pretrained at large scale, transfers zero-shot to a new series. | [T1], [T2] |
| A2 | Timer-XL's real differentiator over base Timer is **cross-series ("channel-dependent")** attention (`TimeAttention`, Kronecker-masked) -- not just a longer context window. | [T2] |
| A3 | *(Code's own reasoning)* A deterministic point forecaster's uncertainty band can be approximated post-hoc from the residual standard deviation of historical log-returns, centered on the model's own point forecast -- not the model's native uncertainty (it has none). | code's own docstring |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Original Timer paper's own curated pretraining corpus (UTSD-12G) | "Up to 1 billion time points" -- the paper's own largest dataset, model sizes 1M-67M params in the paper's own scalability experiments. | [T1] |
| R2 | The specific deployed checkpoint (`thuml/timer-base-84m`) model card | "Univariate pre-trained on 260B time points with 84M parameters," "Context Length: up to 2880." A much larger, later retraining than the original paper's corpus -- not the same number, and not a discrepancy once checked against the checkpoint's own card rather than the original paper. | [T3] |
| R3 | Timer-XL's real differentiator and evaluation | Cross-series `TimeAttention` (Kronecker-masked, channel-dependent) plus RoPE-based position embeddings -- evaluated exclusively on climate/electricity/traffic datasets (ETT, Weather, ECL, Traffic, Solar-Energy, PEMS, EPF, GTWSF, ERA5). **No financial datasets evaluated at all.** | [T2] |
| R4 | Timer-XL's own stated limitation | "The performance of monthly and yearly contexts improves slowly and deteriorates, which may stem from increased noise and training difficulty" -- an open problem the authors flag as future work, not solved. | [T2] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Module docstring states the pretrained checkpoint used "260B time points." | The **original Timer paper** states its own largest curated corpus was "up to 1 billion time points" -- a 260x difference from the code's claim at first read. | **Not a bug -- verified against the actual deployed checkpoint's own model card, not the paper.** `thuml/timer-base-84m`'s Hugging Face card states, in its own words, "univariate pre-trained on 260B time points with 84M parameters" [T3]. The checkpoint was evidently retrained on a much larger corpus after the original paper was published; the code's number matches the *checkpoint*, correctly, not the *paper*. A real lesson from this check: model papers and their later-released checkpoints can diverge significantly, and the checkpoint's own card is the source of truth for what's actually running. |
| F2 | `MAX_CONTEXT = 2880`, applied to the base Timer checkpoint (not Timer-XL). | Timer-XL's own paper describes extending context "from ~1,440 tokens to ~2,880 tokens" as *its* specific improvement over base Timer [T2] -- which, read alone, would suggest 2880 is a Timer-XL-only capability being applied to the wrong (base) checkpoint. | **Also not a bug, again verified against the checkpoint's own card rather than assumed from the paper's framing.** `thuml/timer-base-84m`'s model card states its own "Context Length: up to 2880" directly [T3] -- this specific base-named checkpoint already incorporates the longer-context capability the Timer-XL paper describes, even though it isn't labeled "Timer-XL." The code's constant is correct for the checkpoint actually in use. |
| F3 | Guards `MIN_OBSERVATIONS >= PATCH_SIZE` at import time, raising rather than silently allowing a config that would make the real model permanently unreachable (falling through to the fallback proxy on every call). | -- | **Real, proactive correctness guard** -- prevents a configuration mistake from silently degrading every single call to the fallback without anyone noticing. |
| F4 | Falls back to a patch-mean log-return trend extrapolation (linear fit across patch means) only if the real model fails to load, clearly labeled via `model_backend`/`fallback_reason`. | -- | Same honest-labeling posture as `chronos`/`kronos`/`moirai`/`moment`. |
| F5 | The angle's own name and title promise "Timer / Timer-XL," but only base Timer is ever downloaded or used -- disclosed directly in the docstring's first paragraph. | Timer-XL's real differentiator is genuine cross-series attention, not just longer context [T2] -- and this angle only ever processes one ticker's own series, so that mechanism (like `moirai`'s any-variate attention) wouldn't have anything to attend across even if Timer-XL were used instead. | **Consistent, already-disclosed simplification** -- similar in shape to `kronos`'s honest "Kronos-base, not Kronos-mini/large" disclosure, and, like `moirai`'s any-variate reasoning, the cross-series mechanism Timer-XL actually adds wouldn't be exercisable through this angle's single-symbol interface anyway. |
| F6 | `spec.yaml` carries an explicit, dated changelog note correcting an earlier, stale version of itself (which wrongly claimed no installable package existed). | -- | A concrete, unusual-for-this-codebase practice: documenting a correction to the spec file itself, not just to the code. Positive example of the same self-correcting discipline already seen in several other angles (`shock_clustering`, `shock_personality`, `regime_analysis`). |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | `"pretrained"` = real Timer ran. `"fallback_proxy"` = the patch-mean trend extrapolation ran instead. **Check this first.** |
| `fallback_reason` | Why the fallback fired; `null` when the real model ran. |
| `checkpoint` | `"thuml/timer-base-84m"` when pretrained; absent on fallback. |
| `patch_size` | Always `96`. |
| `n_patches` | How many 96-point patches the (possibly truncated) input was split into. |
| `forecast_horizon` | Always `5`. |
| `last_close` | Last actual close the model saw. |
| `point_forecast` | List of 5 forecasted prices (the model's real, native output on the pretrained path; a patch-trend extrapolation on fallback). |
| `p10_forecast` / `p90_forecast` | **Always post-hoc**, built from historical log-return residual std -- explicitly *not* the model's own uncertainty (the real model is a deterministic point forecaster), same construction on both the pretrained and fallback paths. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | A forecast was produced -- by the real model or the fallback; see `model_backend`. | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default, enforced ≥ `PATCH_SIZE`) closes. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What Timer actually is, and what changed between the paper and the
deployed checkpoint.** The original Timer paper introduced a GPT-style,
patch-based (96-point patches), decoder-only transformer pretrained on a
curated corpus the paper itself caps at "up to 1 billion time points,"
across model sizes up to 67M parameters [T1]. The checkpoint this
codebase actually downloads, `thuml/timer-base-84m`, is a later,
substantially larger retraining -- 260 billion time points, 84M
parameters, and a native context of up to 2880 points -- all stated
directly on the checkpoint's own Hugging Face card [T3], not in the
original paper. Two numbers in this codebase's own docstring initially
looked inconsistent with the paper this research started from, and both
turned out to be accurate once checked against the actual artifact in
use rather than the paper that introduced the architecture.

**Why Timer-XL's real improvement doesn't apply here.** Timer-XL's own
contribution is a genuinely different attention mechanism --
`TimeAttention` with Kronecker-based masking, built specifically to
capture dependencies *across* multiple series (channel-dependence), not
just a longer context window [T2]. This codebase's per-symbol calling
pattern has no second series to attend across, the same structural limit
already documented for `moirai`'s any-variate mechanism. Worth noting
separately: Timer-XL's own paper reports **zero** financial-domain
evaluation -- its benchmark suite is entirely climate/electricity/
traffic data [T2] -- so even setting the single-series limitation aside,
there's no published evidence either way for how Timer-XL specifically
performs on price data.

**What this angle gets right, on balance.** Correct patch size (96,
matching the checkpoint), correct context cap (2880, matching the
checkpoint, verified against its own card), an import-time guard against
a specific, real self-inflicted failure mode (a misconfigured minimum
that would silently disable the real model on every call), and a
documented correction to a previously-stale spec file. Combined with the
already-correct disclosure that this is base Timer, not Timer-XL, this
is the most carefully verified foundation-model angle researched in this
folder so far -- the closest thing to "no real findings" this research
has produced, and that absence is itself worth recording plainly rather
than manufacturing a finding to fill the space.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| T1 | Liu, Zhang, Xu, Wang, Wen, Wang & Long, "Timer: Generative Pretrained Transformer for Time Series Forecasting," arXiv:2402.02368, ICML 2024 (full HTML text) | Original pretraining corpus scale ("up to 1 billion time points," UTSD-12G); patch/segment length S=96; model sizes up to 67M params in the paper's own experiments; confirmed "Finance" domain (Bitcoin) present in the pretraining data table; confirmed "Timer-XL" is not mentioned in this paper at all. | https://arxiv.org/html/2402.02368 |
| T2 | "Timer-XL: Long-Context Transformers for Unified Time Series Forecasting," arXiv:2410.04803 (full HTML text) | TimeAttention (Kronecker-masked, channel-dependent cross-series attention) as the real differentiator from base Timer; RoPE + learnable variable-dimension embeddings; context extended from ~1,440 to ~2,880 tokens during pretraining; zero financial datasets in the evaluation suite (climate/electricity/traffic only); stated open limitation on monthly/yearly context degradation. | https://arxiv.org/html/2410.04803 |
| T3 | Hugging Face model card, `thuml/timer-base-84m` | "Univariate pre-trained on 260B time points with 84M parameters"; "Context Length: up to 2880" -- both quoted directly, used to verify (and rule out) F1/F2 as discrepancies. | https://huggingface.co/thuml/timer-base-84m |
