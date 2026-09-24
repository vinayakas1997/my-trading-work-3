# 11 — lag_llama

- **Angle id:** `lag_llama`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

**`model_backend` is always `"fallback_proxy"` for this angle** -- the
real Lag-Llama model was never installable here (no PyPI package). What
actually runs is a plain AR(5) linear regression on returns, with a
Gaussian quantile band built from its fit residuals -- "the 'lag' part of
the name," in the code's own words, not the real published model.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | *(Real Lag-Llama)* Multi-frequency **lag features** -- values from quarterly, monthly, weekly, daily, hourly and second-level offsets -- given as covariates to a decoder-only transformer capture calendar-aware structure. | [L1] |
| A2 | *(Real Lag-Llama)* A **Student's t-distribution** output head (fitted degrees-of-freedom, mean, scale) is the right way to make the forecast probabilistic. | [L1] |
| A3 | *(This angle's actual fallback)* The next return is a **linear function of its own preceding 5 returns** (a plain AR(5) OLS fit), with **Gaussian**-distributed residuals whose standard deviation widens with √(steps ahead). | code's own design |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Real Lag-Llama, zero-shot, average rank across many downstream benchmark datasets vs. a range of forecasting models (including a simple non-parametric baseline, NPTS) | Average rank **6.714** -- mid-pack, not top of the field, and the paper does not report it beating a plain naive/seasonal-naive forecast. | [L1] |
| R2 | Real Lag-Llama's distribution head | Student's t (heavier tails than Gaussian) -- parameters (degrees of freedom, mean, scale) fitted directly, not assumed fixed. | [L1] |
| R3 | Intraday equity returns, heavy-tailedness (already established for this codebase, see [02-backtesting_44_metrics-angle.md](02-backtesting_44_metrics-angle.md)) | Excess kurtosis ranged **10 to over 1,000** at intraday scale -- real return distributions are far heavier-tailed than Gaussian. | [S5], cited there |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Fallback uses only the **5 immediately preceding returns** as lag features (`LAG_ORDER=5`), nothing calendar-aware. | Real Lag-Llama's actual innovation is **multi-frequency** lag features -- quarterly/monthly/weekly/daily/hourly/second-level offsets, not just "the last few values" [L1]. | **The fallback keeps the name's literal meaning ("lag") but drops the specific mechanism that makes the real model interesting.** A plain AR(5) is a much older, simpler idea than what Lag-Llama actually does -- the code's own docstring is honest about this ("a simple AR fit, not a trained transformer"), but it's worth being precise about *which* part of the design is missing: not just "not a transformer," but specifically "no multi-scale lag structure." |
| F2 | Fallback's quantile band assumes **Gaussian** residuals (`scipy.stats.norm.ppf`). | Real Lag-Llama uses a **Student's t** head specifically because financial/general time series have heavier tails than Gaussian [L1]; this codebase's own research on intraday equity returns found excess kurtosis from 10 to over 1,000 [S5]. | **Real, verifiable mismatch.** A Gaussian band will be too narrow in the tails for the exact kind of data this angle runs on -- p5/p95 will understate how often real moves exceed them, especially at finer timeframes where the fat-tail effect is strongest [S5]. |
| F3 | In `_fit_and_forecast`'s forecasting loop, `price` compounds forward step by step (`price = price * (1 + next_ret)`), but the **quantile spread** at every step is scaled by `closes[-1]` -- the *original* last observed close, not the running `price` variable. | -- (internal inconsistency, code-only) | **Real inconsistency found by tracing the code.** The point forecast correctly compounds multiplicatively, but the uncertainty band's price-scaling stays anchored to the starting price instead of growing with the forecast path. For small per-step returns over a short horizon the difference is negligible, but it means the band's absolute width doesn't track the point forecast's own drift the way a multiplicative random-walk model should -- worth a one-line fix (`price` instead of `closes[-1]` in the `spread` line). |
| F4 | `√(step)` widening of the residual std across the horizon. | Standard for i.i.d. steps (variance is additive, so std scales as √h) -- a reasonable approximation, not literature-contradicted. | Sound as an approximation; doesn't account for the AR(5) structure's own compounding uncertainty (a more careful multi-step AR forecast variance isn't simply √h × one-step variance), but this is a common simplification, not an error. |
| F5 | Glossary and code both explicitly and repeatedly flag `model_backend` as always `"fallback_proxy"`, with a fully-transparent `fallback_reason` (pip install attempt confirmed to fail). | -- | **Exemplary transparency** -- nothing here pretends to be the real model; every field and comment is upfront. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | Always `"fallback_proxy"` -- the real Lag-Llama never runs in this codebase. |
| `fallback_reason` | Fixed explanation: no PyPI package, manual-clone-only research repo, outside the per-model integration budget. |
| `lag_order` | Always `5` -- how many preceding returns the AR fit uses. |
| `forecast_horizon` | Always `5` (bars ahead). |
| `last_close` | Last actual close the fit saw. |
| `point_forecast` | List of 5 compounding price forecasts, one per future bar. |
| `quantile_levels` | Always `[0.05, 0.25, 0.5, 0.75, 0.95]`. |
| `quantile_forecasts` | Dict keyed by quantile level (as strings), each a list of 5 prices -- the Gaussian band around `point_forecast` at each step (see F2/F3 for its real limitations). |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fallback AR fit produced a forecast (there's no separate real-model path to fail into). | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) closes. | + `n_observations`. |

There is **no `fit_failed` status** -- an OLS lag regression on real return
data has no realistic failure mode the way an iterative optimizer
(ARIMA, GARCH, Kalman) does, so none is defined.

## 7. Comprehensive explanation  *(for humans only)*

**What the real Lag-Llama is.** A decoder-only, LLaMA-style transformer
trained on numeric time series (not text), where the key architectural
idea is feeding the model explicit **lag features** -- past values at
multiple calendar-relevant offsets (quarterly, monthly, weekly, daily,
hourly, second-level) -- as covariates, rather than relying purely on
attention over a raw window [L1]. Its output head is a Student's t
distribution rather than a point estimate, so every forecast comes with
a genuine predictive distribution, sampled via autoregressive decoding
to build empirical uncertainty intervals [L1]. Reported zero-shot
performance is solid but mid-pack (average rank 6.714 across many
models) -- not a dominant result even for the real model [L1].

**Why this angle can't run the real thing.** Unlike Kronos or Chronos,
which ship real, pip-or-HuggingFace-downloadable weights, Lag-Llama's
only public artifact at the time this was integrated was a research
GitHub repository requiring a manual clone plus a separately hosted
checkpoint -- confirmed directly by attempting `pip install lag-llama`
and getting "no matching distribution." Rather than skip the angle
entirely, the code fits a genuine (if much simpler) probabilistic model
in its place: ordinary least squares regression of the next return on
its own last 5 returns, with a Gaussian band built from the fit's
residual spread. This keeps *a* real probabilistic forecast in the
system, honestly labeled, rather than either faking a Lag-Llama output
or dropping the angle.

**What's lost in the substitution, precisely (F1/F2).** Two specific
things, not just "it's simpler": first, the real model's multi-scale lag
structure (quarterly through second-level) is exactly what its name
refers to and exactly what's missing -- the fallback only looks at the
5 most recent bars, with no notion of "the same time last week" or "the
same day last month." Second, the real model's choice of a heavy-tailed
Student's t head is a direct response to time series (including
financial data) having fatter tails than Gaussian -- this codebase's own
research on intraday equity returns [S5] found exactly that pattern,
with kurtosis in the hundreds. Using a Gaussian band here specifically
undercuts the one property (genuine tail-aware uncertainty) that the
real model's design was built around.

**The spread-anchoring inconsistency (F3).** This was found by tracing
the loop by hand: `price` is reassigned every iteration to compound the
point forecast forward, but the `spread` calculation multiplies by
`closes[-1]`, captured once before the loop and never updated. Over 5
steps with typical per-bar returns this makes almost no numerical
difference, but it's a real mismatch between how the point forecast and
its uncertainty band are computed, and it would grow more consequential
at longer horizons or on more volatile tickers.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| L1 | Rasul et al., "Lag-Llama: Towards Foundation Models for Probabilistic Time Series Forecasting," arXiv:2310.08278, 2023 (full HTML text) | Definition of lag features (multi-frequency: quarterly/monthly/weekly/daily/hourly/second-level offsets); decoder-only transformer architecture; Student's t-distribution output head (degrees of freedom, mean, scale); autoregressive sampling for uncertainty intervals; zero-shot average rank 6.714 across benchmark datasets and models (incl. NPTS baseline); no stated financial-data-specific caveats. | https://arxiv.org/html/2310.08278 |
| S5 | (Already opened and cited in [02-backtesting_44_metrics-angle.md](02-backtesting_44_metrics-angle.md)) Ratliff-Crain et al., "Revisiting Cont's Stylized Facts for Modern Stock Markets," arXiv:2311.07738 | Reused finding: intraday equity return kurtosis ranges from 10 to over 1,000 -- cited here to support the Gaussian-vs-heavy-tail mismatch (F2). | https://arxiv.org/html/2311.07738 |
| -- | Direct read of `vinu_initial_analysis/angles/lag_llama/compute.py`'s `_fit_and_forecast` | Traced the `price` (compounding) vs. `closes[-1]` (fixed) inconsistency in the quantile spread calculation. | (local code read, 2026-09-24) |
