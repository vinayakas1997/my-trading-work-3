# Bugs Found: Angle 08 — Drawdown Deep-Dive

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Drawdown news attribution always 0% | news_driven_pct=0.0, market_beta_pct=0.0, unexplained_pct=1.0 for all drawdowns | Attribution engine not computing news linkage | None | vinu-correlation | High | Open |
| 2 | Drawdown count varies wildly by ticker volatility | MSFT=3 vs TSLA=102 drawdowns | Fixed threshold (-3%) triggers differently per ticker volatility | None | vinu-correlation | Medium | Open |

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
