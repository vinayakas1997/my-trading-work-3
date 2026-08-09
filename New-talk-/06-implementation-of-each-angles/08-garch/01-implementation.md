---
name: garch-implementation
status: phase-1-done
purpose: the real record of implementing garch's walk-forward backtest against the shared infrastructure — including a real, significant bug found in the shared vinu_tools GARCH estimator itself.
---

# 08 — garch — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/garch/compute.py` | Edited | `MIN_OBSERVATIONS` (renamed from unused-elsewhere naming, raised 20→100). Extracted `_fit_and_forecast()` — and **fixed a real annualization-unit bug in it**, see Bug 1. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/garch/backtest.py` | New | `_garch_step`/`run_garch_backtest` — QLIKE evaluation + secondary vol-direction hit. |
| `vinu-initial-analysis/tests/test_garch.py` | Edited | Strengthened `test_fits_and_forecasts_positive_volatility` with a magnitude sanity bound (see Bug 1/Bug 2 below for why it's `< 10.0`, not tighter). |
| `vinu-initial-analysis/tests/test_garch_backtest.py` | New | 7 tests. |

`spec.yaml` was already at the decided 6 timeframes.

## How it was implemented

Not a price/direction forecaster — forecasts **volatility** (magnitude).
Evaluated with **QLIKE** (`realized_var/forecast_var - ln(realized_var/forecast_var) - 1`,
Patton 2011 — the standard metric in volatility-forecasting research), not
a hit/miss, plus a secondary `vol_direction_hit` (did the forecast
correctly call "rising" vs. "falling" relative to the model's own last
input). No naive-baseline comparison — not part of this angle's decided
design, unlike ARIMA/Chronos/exponential_smoothing.

**Benchmarked real fit cost**: ~0.027s/fit — cheap, no cadence trick
needed, refit every step.

## Testing

7 new tests (synthetic data) + the 4 pre-existing `test_garch.py` tests
(one strengthened). All pass.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars → 25
rows in 1.15s. Tags matched standalone `tag_row`. Storage round-trip and
`query_slice` (by `day_of_week`) both verified exactly against a hand
pandas `groupby`.

## Bugs found

**Bug 1 — real, fixed: annualized/per-period unit mismatch inflated the
volatility forecast by ~5 orders of magnitude.** `vinu_tools.compute.risk.volatility.garch_volatility`'s
`conditional_vol` output is **annualized** (`sqrt(variance_per_period *
annualization_factor)`, confirmed by reading its source). The original
`compute.py` squared this annualized value back
(`conditional_vol[-1] ** 2`) and fed it directly into the GARCH(1,1)
recursion (`omega + alpha*return**2 + beta*last_variance`) — a recursion
that operates on **per-period** variance, the same units `omega` and
`realized_variance` (`actual_next_return**2`) naturally are. This mixed
annualized and per-period quantities. Found via the walk-forward
backtest's real-data check: the very first real forecast came back with
`next_period_variance_forecast = 40.64` against a `realized_variance` of
`0.000194` — obviously wrong, not just "a mediocre forecast."
**Fix 1**: de-annualize before feeding into the recursion
(`last_variance = (conditional_vol[-1]**2) / annualization_factor(time_format)`).
Real result after the fix: forecast dropped from ~40.64 to ~0.19 — a
~214x correction, consistent with de-annualizing by `af=252` for daily
data. This also fixes `compute()`'s existing single-shot output, not just
the new backtest path — every future call to this angle benefits, not
just the walk-forward one.

**Bug 2 — real, found, and now RESOLVED (separate pass, after this angle's
own Phase 1 build): `vinu_tools`'s own GARCH `omega` estimator did not
converge to anything close to the true MLE for realistic return-scale
data.** After Bug 1's fix, QLIKE was still elevated (~5.9, not near 0-1
the way a good fit should land). Traced further: the fitted `omega`
(0.0283 on real AAPL data) was roughly **1,820x larger** than a rough
sanity check would predict (`unconditional_variance × (1 - persistence) ≈
0.0000159`), and this was **not synthetic-data-specific** — confirmed on
real AAPL 1D data directly, not just a hand-built test series. Root cause
traced to `_garch_ml_estimate`'s gradient-ascent optimizer: a **fixed,
unscaled step size** (`1e-8`) applied to `grad_omega = sum(1/sigma2)`,
whose magnitude for realistic (small) variance data is enormous
(`1/sigma2 ≈ 1/0.00002 ≈ 50,000` per observation), producing a huge
first-iteration jump with **no upper bound anywhere in the code** to
correct it. `alpha`/`beta` were clamped to valid ranges by the code's own
`min`/`max` calls, but `omega` was only floored (`max(..., 1e-8)`), never
capped. Worse: the gradient formulas themselves were incomplete — they
treated `sigma2[t]` as depending only directly on `omega`/`alpha`/`beta`,
ignoring the GARCH recursion's own chain-rule dependency on
`sigma2[t-1]` — so no fixed step size could ever have converged correctly.

**The fix** (`vinu-tools/vinu_tools/compute/risk/volatility.py`):
replaced the hand-rolled gradient step entirely with
`scipy.optimize.minimize` (SLSQP) directly minimizing the real Gaussian
negative log-likelihood, with `omega`'s bound tied to the sample variance
(`(1e-12, 10×sample_var)` — the true MLE `omega` is always a fraction of
sample variance via the unconditional-variance identity, so this rules
out the >1000x blowups) and a `alpha + beta ≤ 0.999` stationarity
constraint. **A second, real subtlety found during the fix itself**:
optimizing raw `omega` (~1e-5) jointly with `alpha`/`beta` (~0.05-0.9)
broke SLSQP's internal step-size/convergence logic — it reported
`success: True` after 4 function evaluations while sitting exactly at the
starting guess, with a large unexploited gradient. Confirmed via direct
comparison: minimizing in `log(omega)` space instead (all three
parameters then on a comparable scale) found a genuinely better
optimum (NLL improved from -3662.1 to -3667.8 on the same real data, 16
iterations / 81 evals instead of 4) — this is the version that shipped.
Verified robust via a 5-different-starting-points check on a real 124-return
AAPL window: all five converge to the exact same solution.

**Real, measured impact — before vs. after, same real AAPL data**: fitted
`omega` now lands within ~1.01x-1.05x of the variance-targeting sanity
identity (was ~1,820x off). On a 125-bar real AAPL walk-forward re-run,
mean `qlike_error` dropped from ~5.9 (elevated, before) to ~2.25 (after) —
`next_period_variance_forecast` no longer systematically inflated.

**Why this was a separate pass, not inline here**: `_garch_ml_estimate`/
`garch_volatility` are shared `vinu_tools` functions — `shock_personality`
uses the exact same function internally for its `vol_persistence` field
(confirmed by `test_garch.py::test_matches_shock_personality_vol_persistence_fit`,
which asserts `garch`'s and `shock_personality`'s fits are identical —
they still are, post-fix). Fixing a shared numerical-methods bug with a
two-angle blast radius needed its own benchmarked before/after, not a
side-quest inside this angle's own backtest wiring. Both angles' full
test suites (26 tests) and the wider monorepo's consumers of
`garch_volatility` (`vinu-live`, `vinu-portfolio`, `vinu-research`, 53
tests combined) were re-run after the fix — all pass, no regressions.

**Tracked separately, not just here**: `../known-issues.md` Resolved #2,
with the full before/after — kept as its own cross-angle tracker entry
(affected `shock_personality` too, not just this angle) so it stayed
discoverable and combinable with other shared-library issues, rather than
buried inside one angle's implementation record.

**Full `vinu-initial-analysis` suite**: 260 passed (up from 253
pre-this-angle — the 7 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures at the time this angle was
first built (later resolved by those angles' own rewrites, unrelated to
Bug 2), no new failures.

## Related files

- `02-real-scenario.md` — the real example, with both bugs' effects shown concretely.
- `00-plan.md` — the pre-implementation plan.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/08-garch.md` — the decided design.
