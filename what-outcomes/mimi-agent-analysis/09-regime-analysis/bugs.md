# Bugs Found: Angle 09 — Regime Analysis

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|   |-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Regime Sharpe values are extremely large (bull SR=37) | No error — but Sharpe values are unrealistic | Classification uses contemporaneous returns — regime label and returns are from same period, creating circular logic | None | angle09_regime.py | Medium | Open |
| 2 | Synthetic fallback cumsum flattens array | `ValueError: Shape of passed values is (2000, 1)` | `np.random.randn(500,4).cumsum()` without axis flattens to (2000,) | Changed to `.cumsum(axis=0)` | angle09_regime.py | Critical | Fixed |

## Notes
- The 70th percentile volatility threshold is arbitrary; different thresholds produce different regime distributions
- A forward-looking (ex-ante) regime definition would: use vol from prior N days, classify before computing returns

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
