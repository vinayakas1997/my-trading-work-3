# Bugs Found: Angle 23 — Event Study Methodology

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Events API returns significance="?" for all events | No error — all events have significance="?" | Event significance not pre-computed in correlation service | None | vinu-correlation | High | Open |

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
