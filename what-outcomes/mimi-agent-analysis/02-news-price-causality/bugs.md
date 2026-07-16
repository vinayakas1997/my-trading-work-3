# Bugs Found: ANGLE 02 - News-Price Causality (Statistical Proof)

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | `/story/{ticker}` returns HTTP 500 | `HTTP 500: Internal Server Error` | `PriceClient.get_candles()` doesn't accept `days` parameter — only `from_ts`/`to_ts` | Changed `days=30` to `from_ts=now_ts-30*86400, to_ts=now_ts` | vinu-correlation/vinu_correlation/api.py:265 | Medium | Fixed |
| 2 | `/strategies/{name}/evaluate` returns HTTP 500 | `HTTP 500: Internal Server Error` | Two root causes: (a) Strategy service not started with `VINU_STRATEGY_STRATEGIES_DIR`, (b) Expression engine crashed on ZeroDivisionError | (a) Restarted with strategies dir, (b) Added `ZeroDivisionError → nan` guard | vinu-strategy/engine/expression.py:81 | Critical | Fixed |
| 3 | Correlation data all zero (sample_size=0) | `news_return_corr: 0.0, sample_size: 0, granger_p_value: 1.0` | Correlation computation at query time doesn't find overlapping hourly data | Events stored (227 for AAPL), but hourly resample produces no overlap | vinu-correlation/engine/ | High | Open |
| 4 | Price reaction fields all null in impact events | `price_change_5m: null, price_change_15m: null, price_change_30m: null, price_change_1h: null` | Price reaction computation not triggered or depends on missing correlation data. | Not yet fixed | vinu-correlation/engine/impact.py | High | Open |
| 5 | Drawdown attribution shows 0% news-driven | `news_driven_pct: 0.0, contributing_events: []` | Contributing event linking not populated. All drawdowns 100% unexplained. | Not yet fixed | vinu-correlation/engine/drawdown.py | Medium | Open |
| 6 | `adx_14` unknown in price endpoint indicators | `HTTP 400: Unknown indicators: adx_14` | Price endpoint built-in indicators do not include ADX. Only SMA_5/10/20/50, RSI_14, MACD, daily_return, volatility_20d. ADX available via features service (8082). | Changed to `sma_10,sma_20,rsi_14` | angle02_query.py:171 | Low | Fixed |

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
