# Bugs Found: Angle 12 — Benchmark Comparison

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | SPY not in price catalog | SPY returns 0 bars from /candles/SPY | SPY not provisioned in data catalog — no historical data loaded | None | vinu-stock-price | High | Open |

## Notes
- NVDA used as benchmark proxy instead of SPY
- Results reflect sector-specific correlation (all tickers are tech), not broad-market beta

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
