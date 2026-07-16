# Bugs Found: Angle 07 — Session/Time-of-Day Analysis

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Correlation API missing session_correlations field | /correlation/{ticker} response lacks session_correlations key | API returns correlation=? with no session breakdown | None | vinu-correlation | Medium | Open |
| 2 | Correlation API returns sample_size=0 for all tickers | All correlation values = 0 with sample_size=0 | Data not pre-computed in correlation service | None | vinu-correlation | High | Open |

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
