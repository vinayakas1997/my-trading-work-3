# 07 — garch

- **Angle id:** `garch`
- **Cluster:** C — Volatility & drawdown risk
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/garch/`
  (`compute.py`, `backtest.py`, `spec.yaml`); shared fit engine:
  `vinu-tools/vinu_tools/compute/risk/volatility.py` (`garch_volatility`,
  `_garch_ml_estimate`) -- the same function `shock_personality` uses
  internally for its own `vol_persistence` field.
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Fits a GARCH(1,1) model to recent returns -- today's variance depends on
yesterday's surprise and yesterday's variance -- and forecasts next
period's volatility (magnitude of moves), not direction. Reuses the same
fit `shock_personality` already computes internally, exposed here as its
own first-class result.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Variance follows `h_t = omega + alpha * shock_{t-1}^2 + beta * h_{t-1}` -- today's variance depends on yesterday's squared surprise and yesterday's variance ("an adaptive learning mechanism"). | [G1] |
| A2 | Stationarity requires `alpha + beta < 1`. | [G1] |
| A3 | Positive and negative return shocks of the same size affect future volatility **equally** (plain GARCH is symmetric). | code's own design (uses `garch_volatility`, not `egarch_volatility`) |
| A4 | The correct way to compare volatility forecasts across models is a loss function that stays robust when using an imperfect proxy (e.g. squared returns) for true variance. | [G2] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Ranking volatility forecasts using 9 common loss functions, imperfect proxy | Only **MSE** and **QLIKE** are "robust" -- give the same ranking of competing forecasts whether the true variance or a conditionally-unbiased proxy (like squared returns) is used. The other 7 can flip the ranking. | [G2] |
| R2 | QLIKE loss, definition | `L(proxy, forecast) = log(forecast) + proxy / forecast` -- depends only on the *standardized* forecast error (`proxy / forecast`), which is why it's robust to proxy noise. | [G2] |
| R3 | Japanese daily stock returns, comparing symmetric vs. asymmetric ARCH-family models via the "News Impact Curve" | The best-fitting models were the **asymmetric** ones (GJR and Nelson's EGARCH) -- negative shocks moved future volatility differently (more) than positive shocks of the same size. | [G3] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Fits plain symmetric GARCH(1,1) (`garch_volatility`, not `egarch_volatility`, though `egarch_volatility` already exists in the same shared module). | Asymmetric models (GJR, EGARCH) fit real equity return data better than symmetric GARCH because negative and positive shocks affect future volatility differently [G3]. | **Known, real limitation, not a bug.** A down day and an up day of the same size are currently treated as equally informative about tomorrow's volatility. The fix already exists in the same file (`egarch_volatility`) but nothing wires it into this angle. |
| F2 | Optimizer bounds enforce `alpha + beta <= 0.999` (`_garch_ml_estimate`'s constraint). | Stationarity requires `alpha + beta < 1` exactly [G1, Theorem 1]. | **Correct**, matches the literature's condition with a small safety margin below 1. |
| F3 | `compute.py`'s own code comment documents a bug it **already found and fixed**: squaring the *annualized* conditional volatility straight into the per-period variance recursion would inflate the forecast by the annualization factor (`af`, e.g. 252x for daily data) -- caught via the walk-forward backtest returning a forecast "~5 orders of magnitude larger than the realized variance," fixed by de-annualizing (`conditional_vol[-1]**2 / af`) before feeding it back into the recursion. | Standard GARCH recursion operates on per-period variance [G1]. | **Verified correct as currently written** -- traced the indexing by hand: `garch_volatility`'s last returned value is the variance forecast for the last observed period conditional on the period before it; `compute.py` correctly advances that one more step using the *last* actual return. No live bug found here, but worth recording since it's the kind of unit-mixing error easy to reintroduce. |
| F4 | Evaluates backtest accuracy with QLIKE, defined as `realized/forecast - log(realized/forecast) - 1`. | Patton's own QLIKE, Eq. (6): `log(forecast) + proxy/forecast` [G2]. | **Not literally the same formula**, but the two differ only by an additive constant that doesn't depend on the forecast (`-log(proxy) - 1`), so they rank competing forecasts identically for the same realized outcome -- the robustness property [G2] still holds. The variant used here has the convenient extra property that it equals exactly 0 at a perfect forecast (`ratio == 1`), which the raw paper formula does not. |
| F5 | No `naive_baseline.py` for this angle; `backtest.py`'s own docstring says this was a **deliberate decision** ("not part of the decided design for this angle (unlike ARIMA/Chronos/exponential_smoothing)"). | -- | Documented choice, not an oversight -- flagged here only because every other angle researched so far that lacks one (`dlinear`) turned out to be missing it by omission, not decision; this one is different. |
| F6 | `MIN_OBSERVATIONS` raised from a floor of 20 to 100 (config default), same consistency move as the other classical angles. | -- (internal decision) | Consistent with `arima`/`dlinear`/`exponential_smoothing`; no new finding. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `next_period_volatility_forecast` | Forecasted standard deviation of the next period's return (per-period units, not annualized -- see F3). |
| `next_period_variance_forecast` | The same forecast, squared (variance instead of volatility). |
| `alpha` | Weight on yesterday's squared return shock. Higher = volatility reacts more sharply to fresh surprises. |
| `beta` | Weight on yesterday's variance. Higher = volatility persists longer once elevated. |
| `omega` | The baseline variance level the recursion reverts toward. |
| `persistence` | `alpha + beta`. Close to 1 means today's volatility regime is expected to keep going, not mean-revert quickly (matches the glossary's own description). |
| `n_observations` | How many returns were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fit succeeded, forecast produced. | All fields above. |
| `no_data` | No price bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) returns. | + `n_observations`. |

Unlike `exponential_smoothing`, there is **no `fit_failed` status** written
by `compute()` itself -- `_fit_and_forecast` can raise, but `compute()`
does not catch it the way `backtest.py`'s `_garch_step` does (that one
explicitly wraps the call in `try/except` and returns `status:
"fit_failed"`). An uncaught fit failure in the live path would propagate
as an exception, not a graceful status row.

## 7. Comprehensive explanation  *(for humans only)*

**What GARCH(1,1) is.** Bollerslev's 1986 generalization of Engle's ARCH
model: instead of variance depending only on a fixed window of past
squared shocks, it depends on yesterday's squared shock **and**
yesterday's own variance estimate, `h_t = omega + alpha*shock_{t-1}^2 +
beta*h_{t-1}` [G1]. That one extra term is what lets GARCH(1,1) behave
like an infinite-memory ARCH model with just three parameters -- Bollerslev
calls it "some sort of adaptive learning mechanism" [G1]. Stationarity
(the process has a well-defined, finite long-run variance) requires
`alpha + beta < 1` [G1, Theorem 1]; our optimizer's bound of 0.999
enforces this directly.

**Why the shared fit function is used, not a fresh one.** `garch` and
`shock_personality` both need "how persistent is this ticker's
volatility regime" -- `garch_volatility` is the one place that logic
lives, and this angle exposes its forecast as a first-class result
instead of duplicating the optimization code, per the module's own
docstring.

**The annualization bug the code already caught (F3).** GARCH's own
recursion works in per-period variance units. `garch_volatility`
additionally returns an *annualized* volatility series for convenience
(useful for e.g. comparing across timeframes), computed as `sqrt(variance
* annualization_factor)`. The trap: squaring that annualized number back
and feeding it straight into the next-step recursion mixes annualized and
per-period units, inflating the forecast by the annualization factor
itself (252x on daily data). The code comment documents finding this the
hard way -- a real-data backtest returned a forecast five orders of
magnitude too large -- and fixing it by dividing the squared annualized
value back down by the same factor before using it. Hand-tracing the
indexing (F3 row) confirms the fix is applied correctly and consistently
with the recursion's own definition of "variance conditional on
everything through the period before."

**The symmetry gap (F1).** Plain GARCH treats a $5 drop and a $5 rally
the same when forecasting tomorrow's volatility. Real equity data
disagrees: Engle & Ng's own comparison of ARCH-family models on stock
returns found the best-fitting ones were specifically the asymmetric
ones (GJR, Nelson's EGARCH), which let negative shocks move future
volatility by more than positive shocks of the same size [G3]. Nothing
in this angle is broken by using symmetric GARCH -- it is a real,
long-established simplification, and the module already has
`egarch_volatility` sitting unused a few lines away in the same file if
that gap is ever worth closing here.

**Reading QLIKE (F4).** QLIKE's real appeal, per Patton, isn't just that
it's a common metric -- it's one of only two loss functions (with plain
MSE) whose *ranking* of competing volatility forecasts stays the same
regardless of which imperfect proxy for "true" variance is used to
evaluate them [G2]. The exact formula used in `backtest.py`
(`ratio - log(ratio) - 1`) isn't character-for-character Patton's
Eq. (6), but the difference is a constant that doesn't depend on the
forecast being scored, so it preserves that same robustness property
while also reading naturally as "0 = perfect forecast."

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| G1 | Tim Bollerslev, "Generalized Autoregressive Conditional Heteroskedasticity," *Journal of Econometrics* 31 (1986), pp. 307-310 (original PDF, pp. 1-4) | GARCH(p,q)/GARCH(1,1) variance equation; parameters `omega`/`alpha`/`beta`; Theorem 1's stationarity condition `A(1) + B(1) < 1`. | https://public.econ.duke.edu/~boller/Published_Papers/joe_86.pdf |
| G2 | Andrew J. Patton, "Volatility forecast comparison using imperfect volatility proxies," *Journal of Econometrics* 160 (2011), pp. 246-251 (full PDF, pp. 1-6) | Definition of a "robust" loss function; only MSE and QLIKE are robust among 9 common loss functions; QLIKE formula `log h + proxy/h` (Eq. 6); robustness depends only on the standardized forecast error. | https://public.econ.duke.edu/~ap172/Patton_vol_proxies_JoE_2011.pdf |
| G3 | Robert F. Engle & Victor K. Ng, "Measuring and Testing the Impact of News on Volatility," NBER Working Paper No. 3681, April 1991 (PDF, pp. 1-3) | Introduces the News Impact Curve; comparison across ARCH-family models on Japanese daily stock returns found the best-fitting models were the asymmetric ones (GJR, Nelson's EGARCH). | https://www.nber.org/system/files/working_papers/w3681/w3681.pdf |
