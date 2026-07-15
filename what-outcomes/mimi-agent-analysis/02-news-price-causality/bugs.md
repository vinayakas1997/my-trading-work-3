# Bugs Found: ANGLE 02 - News-Price Causality (Statistical Proof)

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | `/story/{ticker}` returns HTTP 500 or timeout | `HTTP 500: Internal Server Error` / Read timeout | Server-side error in vinu-correlation story/thread tracking. Likely missing data or unhandled edge case. | Not yet fixed | vinu-correlation/server/routes_read.py | Medium | Open |
| 2 | `/strategies/{name}/evaluate` returns HTTP 500 | `HTTP 500: Internal Server Error` | Strategy service health shows "Service not initialized". Evaluation endpoint fails due to uninitialized state. | Not yet fixed | vinu-strategy/service.py | Critical | Open |
| 3 | Correlation data all zero (sample_size=0) | `news_return_corr: 0.0, sample_size: 0, granger_p_value: 1.0` | Correlation computation pipeline not triggered. No historical data pre-computed. | Not yet fixed | vinu-correlation/engine/ | High | Open |
| 4 | Price reaction fields all null in impact events | `price_change_5m: null, price_change_15m: null, price_change_30m: null, price_change_1h: null` | Price reaction computation not triggered or depends on missing correlation data. | Not yet fixed | vinu-correlation/engine/impact.py | High | Open |
| 5 | Drawdown attribution shows 0% news-driven | `news_driven_pct: 0.0, contributing_events: []` | Contributing event linking not populated. All drawdowns 100% unexplained. | Not yet fixed | vinu-correlation/engine/drawdown.py | Medium | Open |
| 6 | `adx_14` unknown in price endpoint indicators | `HTTP 400: Unknown indicators: adx_14` | Price endpoint built-in indicators do not include ADX. Supports only SMA, RSI, daily_return, volatility_20d. Must use features service (8082) for ADX. | Not a bug — price service limitation. ADX via features service (8082). | vinu-stock-price/ | Low | By Design |

## Notes
- **Bug #2** (strategy evaluate) is critical — blocks any strategy-based angle (03, 08, 09, 10, 11, 12, etc.)
- **Bug #3** (correlation data) blocks all correlation-based analysis for Angle 02
- Bug #4 and #5 are downstream effects of #3
- Bug #1 and #3 were also found in Angle 01

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
