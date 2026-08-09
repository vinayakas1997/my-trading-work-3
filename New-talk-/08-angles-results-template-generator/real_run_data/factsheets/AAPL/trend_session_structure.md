# trend_session_structure (AAPL) -- Trend Session Structure

**trend_session_structure (AAPL):** Session-level analysis of trend_lifecycle peaks/troughs — which trading session (premarket/regular/afterhours) produces reliable tops, with per-session drawdown, recovery, and match-similarity statistics Output: Angle-specific results

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H). Each cell states `n_signals`, `n_mature_signals`, `avg_stated_confidence`, `measured_success_rate`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H |
|---|---|---|---|---|---|
| closed | not available | not available | not available | not available (n=0) | not available |
| london | not available | not available | not available | not available (n=0) | not available |
| ny_premarket | not available | not available | not available | not available (n=0) | not available |
| ny_regular | not available | not available | not available | not available (n=0) | not available |
| ny_afterhours | not available | not available | not available | not available (n=0) | not available |

## Status counts by time format
1H: meets_floor = False: n=1 (of 2)
1H: meets_floor = True: n=1 (of 2)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/trend_session_structure`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1H/{time_range}/trend_session_structure/c59543c6859f` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1H numbers came from). This document states values only -- it does not compare, rank, or advise between them._