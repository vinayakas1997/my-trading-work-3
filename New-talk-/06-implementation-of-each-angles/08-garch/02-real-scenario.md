---
name: garch-real-scenario
status: phase-1-done
purpose: one concrete, real example proving garch's walk-forward backtest architecture works — and showing, concretely, the real bug found and fixed (and the real bug found and not yet fixed) along the way.
---

# 08 — garch — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used by every prior
Phase-1 `1D` check this session.

## The call

```python
from vinu_initial_analysis.angles.garch.backtest import run_garch_backtest

df = run_garch_backtest("AAPL", "1D", bars)  # 25 rows, 1.15s
```

## Real output — first row (as originally shipped, Bug 2 not yet fixed)

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1782950400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "thursday", "week_of_month": 1, "month": 7, "quarter": 3,
  "status": "ok", "n_observations": 99,
  "next_period_volatility_forecast": 0.4355,
  "next_period_variance_forecast": 0.1897,
  "alpha": 0.1000, "beta": 0.8505, "omega": 0.0283, "persistence": 0.9505,
  "actual_next_return": 0.01394, "realized_variance": 0.000194,
  "qlike_error": 5.8843,
  "forecasted_vol_direction": "rising", "actual_vol_direction": "falling",
  "vol_direction_hit": 0
}
```

## Bug 1, shown concretely: before vs. after the annualization fix

| | `next_period_variance_forecast` | `qlike_error` |
|---|---|---|
| Before fix (annualized value fed into per-period recursion) | 40.64 | 11.25 |
| After fix (de-annualized correctly) | 0.19 | 5.88 |

A ~214x correction — consistent with dividing out the `af=252` daily
annualization factor. This is a real bug that existed in `compute.py`
before this session touched it; fixed for both the new backtest path and
the existing single-shot `compute()` output.

## Bug 2, shown concretely: real AAPL data, not just a hand-built test — now fixed

**Original finding** (this angle's own Phase 1 pass):

```python
from vinu_tools.compute.risk.volatility import garch_volatility

returns = bars["close"].pct_change().dropna().values
# real AAPL daily returns: std=0.0179, var=0.000321
cv, alpha, beta, omega = garch_volatility(returns, fit=True, time_format="1D")
# alpha=0.1000, beta=0.8506, omega=0.0289

expected_omega_rough = returns.var() * (1 - alpha - beta)
# ~0.0000159 -- the real fitted omega (0.0289) is ~1,820x larger
```

This was a real, then-open issue in the shared
`vinu_tools._garch_ml_estimate` optimizer (a fixed, unscaled gradient
step for `omega`, with no upper bound, and gradient formulas that ignored
the GARCH recursion's own chain-rule dependency on the prior step's
variance) — not specific to synthetic test data or to this angle. It also
affected `shock_personality`, which uses the identical function.

**After the fix** (separate pass — `scipy.optimize.minimize` on the real
negative log-likelihood, optimized in `log(omega)` space; full
investigation in `known-issues.md`'s Resolved section), same real AAPL
125-bar slice:

```python
cv, alpha, beta, omega = garch_volatility(returns, fit=True, time_format="1D")
# alpha=0.1741, beta=0.0000, omega=0.000160

expected_omega_rough = returns.var() * (1 - alpha - beta)
# ~0.000169 -- omega is now within ~0.95x, not ~1820x
```

Note `beta` genuinely converges to ~0 on this particular 125-bar window
(confirmed stable across 5 different optimizer starting points, not an
artifact) — a real MLE finding that this slice's squared-return sequence
doesn't show strong multi-lag volatility persistence beyond one lag, not
a bug.

## Storage + query round-trip, for real (re-run after the Bug 2 fix)

```python
storage.write("AAPL", "garch", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "garch", granularity="1D", tier="tier2")

query_slice(back, ["day_of_week"], {"avg_qlike": ("qlike_error", "mean")})
# mean qlike_error across 25 rows: ~2.25 (was ~5.9 before the Bug 2 fix)
```

Matched a hand-computed pandas `groupby` exactly, same as before the fix.

## What this scenario actually proves

The walk-forward architecture (tagging, storage, query, real-data wiring)
works correctly end to end for this angle, Bug 1 (a real, serious
unit-mismatch bug) is genuinely fixed, and — as of the follow-up pass
documented in `known-issues.md` — Bug 2's upstream `omega` estimator is
also genuinely fixed, verified on the same real AAPL data this scenario
originally used to find it.

## Related files

- `01-implementation.md` — the full bug investigation.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this scenario satisfies (architecturally).
