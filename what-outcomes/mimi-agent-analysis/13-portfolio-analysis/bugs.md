# Bugs Found: Angle 13 — Portfolio Analysis

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | `rolling['s'].cov(rolling['ref'])` raises `ValueError` because `rolling.cov()` expects a Series/DataFrame, not Rolling column access | `ValueError: other must be a DataFrame or Series` | Pandas ≥2.x Rolling.cov() API change — inline rolling access disallowed | Changed to `combined['s'].rolling(60).cov(combined['ref'])` | `angle13_portfolio.py:89` | Medium | Fixed |

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
