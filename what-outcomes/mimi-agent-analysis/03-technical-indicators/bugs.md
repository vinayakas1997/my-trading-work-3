# Bugs Found: ANGLE 03 - Technical Indicator Landscape

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| | | | | | | | |

## Notes
- All 24 indicator kinds work correctly across all tickers and timeframes
- ADX (`adx_14`) is not available in the price endpoint's built-in indicators (port 8081) — this is expected, ADX is available via the features service (port 8082)
- Indicator warmup periods are expected behavior (SMA needs N bars before producing values)
- No new bugs found in Angle 03

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
