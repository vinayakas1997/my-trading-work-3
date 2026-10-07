# 14 — moirai

- **Angle id:** `moirai`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/moirai/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

**`model_backend` is always `"fallback_proxy"` for this angle.** The real
MOIRAI would need a dependency install that downgrades this whole
environment's shared torch build, and even installed, its defining
feature -- attending across many tickers' series jointly -- can't be
exercised through this codebase's one-symbol-at-a-time interface. What
runs instead is a plain AR(3) fit with an 80% (p10/p90) Gaussian band,
`any_variate_note` making the single-ticker degeneration explicit.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | *(Real MOIRAI)* Flattening several series into one sequence and using **learned attention bias terms** that distinguish "same variate" from "different variate" token pairs lets one model jointly attend across an arbitrary number of input series. | [M1] |
| A2 | *(Real MOIRAI)* This mechanism is permutation-equivariant to variate ordering and permutation-invariant to variate identity -- it doesn't matter which order tickers are fed in, or which specific tickers they are. | [M1] |
| A3 | *(Code's own reasoning)* With only **one** variate (this angle's actual calling pattern), any-variate attention has no cross-variate term left to compute, so it collapses to ordinary single-series attention -- no real capability is lost by degrading gracefully, but none of the model's distinguishing mechanism is exercised either. | code's own docstring, corroborated by [M1] |
| A4 | *(This angle's actual fallback)* An AR(3) fit on returns, with a Gaussian band whose width scales with √(horizon), approximates "a genuinely probabilistic single-series forecast" well enough to stand in. | code's own design |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Real MOIRAI, zero-shot vs. full-shot (trained-on-the-target-data) models, general benchmark suite | "Competitive or superior performance as a zero-shot forecaster when compared to full-shot models" -- a general claim, not specific to any one dataset. | [M1] |
| R2 | Model sizes | `small` 14M, `base` 91M, `large` 311M parameters. | [M1] |
| R3 | Pretraining domain coverage (LOTSA corpus) vs. financial data specifically | Includes an "Econ/Fin" domain (e.g. M4 Monthly, Bitcoin), but **no dedicated stock-price or exchange-rate benchmark results are reported anywhere in the paper.** | [M1] |
| R4 | `uni2ts` package's real dependency constraints | `torch>=2.1,<2.5`, plus `lightning>=2.0`, `jax[cpu]`, and `tensorboard` (unpinned). | [M2] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | In `_forecast_ar`, the point forecast compounds forward (`price = price * (1 + next_ret)`), but the **quantile spread** is scaled by `float(closes[-1])` -- the fixed original close -- at every horizon step, not by the compounding `price`. | -- (internal inconsistency, code-only) | **The exact same bug already found in `lag_llama`'s `_fit_and_forecast`** (see [11-lag_llama-angle.md](11-lag_llama-angle.md), F3) -- same anchoring mistake, in a structurally near-identical fallback function. Since both angles share the same AR-plus-Gaussian-band fallback pattern, this looks like it was copied from one to the other along with the bug. Same fix applies: use the running `price`, not `closes[-1]`. |
| F2 | Code comment states `uni2ts` "pulls in `torch==2.4.1` as a hard dependency." | The real constraint in `uni2ts`'s own `pyproject.toml` is a **range**, `torch>=2.1,<2.5`, not a pin to exactly `2.4.1` [M2]. | **Minor factual imprecision, conclusion still correct.** The practical consequence the comment is warning about -- installing `uni2ts` would force downgrading this environment's torch (2.13/2.14, per other angles' direct container tests) below 2.5 -- is accurate and, if anything, *understated*: the real cap is `<2.5`, further from the installed version than a single pinned `2.4.1` might suggest. The jax/lightning/tensorboard dependency-tree claim is fully confirmed [M2]. |
| F3 | Code's reasoning that a single-symbol call degenerates any-variate attention to ordinary attention, "same as Chronos/TimesFM." | Confirmed directly: the mechanism's cross-variate term only exists when there's more than one variate to compare against; the paper's own formulation reduces to standard attention at `d_y=1` [M1]. | **Correct reasoning, verified against the paper's actual mechanism**, not just assumed plausible. |
| F4 | Falls back rather than attempting a real install. | No dedicated financial benchmark exists for real MOIRAI even if it had been installed [M1, R3]. | Even setting aside the dependency risk and the single-variate degeneration, the real model's own published evidence base doesn't include stock/equity data -- unlike `kronos`, which is finance-specific and does report real market benchmarks. Skipping the risky install here costs less unrealized value than it might for a finance-specific model. |
| F5 | `p10_forecast`/`p90_forecast` use z=1.2816 (the correct normal-distribution 10th/90th percentile z-score). | -- (arithmetic check) | Correct value, verified. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | Always `"fallback_proxy"` -- the real MOIRAI never runs here. |
| `fallback_reason` | Explains the torch-downgrade risk and the structural any-variate limitation. |
| `any_variate_note` | Explicit statement that this call is single-ticker only, not exercising MOIRAI's real differentiator. |
| `forecast_horizon` | Always `5` (bars ahead). |
| `last_close` | Last actual close the fit saw. |
| `point_forecast` | List of 5 compounding price forecasts. |
| `p10_forecast` / `p90_forecast` | 10th/90th percentile Gaussian band around the point forecast at each step -- **see F1** for the same fixed-anchor spread issue found in `lag_llama`. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fallback AR fit produced a forecast. | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) closes. | + `n_observations`. |

No `fit_failed` status -- same reasoning as `lag_llama`: a closed-form OLS
fit on real return data has no realistic optimizer failure mode.

## 7. Comprehensive explanation  *(for humans only)*

**What MOIRAI's real differentiator is.** Most time-series foundation
models (Chronos, TimesFM) are univariate: one call, one series. MOIRAI's
distinguishing idea is handling an *arbitrary number of series jointly*
in one call, by flattening them into a single token sequence and adding
learned bias terms to the attention scores that tell the model whether
two tokens come from the same series or different ones -- this is what
lets it jointly reason about, say, many tickers at once, in a way that's
insensitive to which order they're given in [M1]. It comes in three
sizes (14M/91M/311M) and is reported competitive with models trained
specifically on the target data, though the paper never tests it on
stock or exchange-rate data directly [M1].

**Why the real model can't help here even before the dependency
problem.** This codebase's angle interface calls `compute()` once per
symbol with that symbol's own bars -- there's no path to hand MOIRAI
several tickers' series in one call. Verified directly against the
paper's own formulation: any-variate attention's whole mechanism is
built from cross-variate bias terms that simply don't exist when there's
only one variate present, so even a perfectly-installed real MOIRAI
would run as an ordinary, single-series model here -- the code's
reasoning for not bothering with the real weights is sound, not just an
excuse.

**The dependency risk, precisely (F2).** `uni2ts` isn't pinned to one
exact torch version -- it accepts a range, `2.1` up to (but not
including) `2.5`. Since this whole codebase's shared environment runs
torch 2.13/2.14 (confirmed via direct container tests for other angles,
e.g. `04-dlinear-angle.md`), installing `uni2ts` as stated would force a
major downgrade across every other angle and service sharing that
environment -- a real, correctly-identified risk, just described with
slightly more precision (a pin) than the actual constraint (a range) has.

**The same bug as `lag_llama` (F1).** Both angles share nearly the same
fallback shape: compound a point forecast forward with an AR fit, then
build a Gaussian band around it. Both compute that band's width by
multiplying a residual-based spread by the *original* last close instead
of the *compounding* forecast price at each step. Given how close the
two functions are in structure and naming (`_fit_and_forecast`,
`spread = resid_std * np.sqrt(steps) * float(closes[-1])` in both), this
looks like the same underlying pattern reused across both fallback
proxies -- worth fixing in both places together, not just one.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| M1 | Woo, Liu, Kumar, Xiong, Savarese & Sahoo, "Unified Training of Universal Time Series Forecasting Transformers" (MOIRAI), arXiv:2402.02592 (full HTML text) | Any-variate attention mechanism (flattening + RoPE + learned same/cross-variate bias terms); permutation equivariance/invariance properties; model size table (small/base/large parameters); zero-shot vs. full-shot performance claim; confirmation of no dedicated financial benchmark results, despite an "Econ/Fin" pretraining domain including Bitcoin. | https://arxiv.org/html/2402.02592 |
| M2 | `uni2ts` package's `pyproject.toml`, `SalesforceAIResearch/uni2ts` GitHub repo, `main` branch | Real dependency constraints: `torch>=2.1,<2.5`, `lightning>=2.0`, `jax[cpu]`, `tensorboard` (unpinned), `gluonts~=0.14.3`, and others. | https://raw.githubusercontent.com/SalesforceAIResearch/uni2ts/main/pyproject.toml |
