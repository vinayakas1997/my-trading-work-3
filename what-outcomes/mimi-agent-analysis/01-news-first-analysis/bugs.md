# Bugs Found: ANGLE 01 - News-First Analysis

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | `/candles/{symbol}` with `days` param returns 0 bars | `{"count":0,"data":[]}` | `days` parameter calculation likely has timezone/offset issue in `vinu-stock-price` service | Workaround: use `from`/`to` Unix timestamps instead of `days`. Need root cause analysis in service. | vinu-stock-price/server/routes_read.py | High | Open |
| 2 | `/story/{ticker}` endpoint returns HTTP 500 for all tickers | `HTTP 500: Internal Server Error` | Server-side error in `vinu-correlation` story/thread tracking. Likely missing data or unhandled edge case in story endpoint logic. | Not yet fixed. Need to check `vinu-correlation` server routes. | vinu-correlation/server/routes_read.py | Medium | Open |
| 3 | Price correlation values are all zero (sample_size=0) | `news_return_corr: 0.0, sample_size: 0` | Correlation data may need pre-computation or a separate trigger endpoint to populate. The `/correlation/{ticker}` endpoint has no data to analyze. | Not yet fixed. May need to run correlation computation pipeline. | vinu-correlation/engine/ | Medium | Open |

## Notes
- **Bug #1** (days param): Also note that interval values must be lower-case (`1d`, `1h`, `15m`), not capitalized (`1Day`, `1Hour`, `15Min`).
- **Bug #3**: Impact event price_change fields (5m/15m/30m/1h) are also all `null`, suggesting price reaction computation is not triggered automatically.
- `/high-impact` has max `hours=720` constraint — this is by design, not a bug.

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
