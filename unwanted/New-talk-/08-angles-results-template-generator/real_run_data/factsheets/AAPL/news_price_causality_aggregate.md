# news_price_causality_aggregate (AAPL) -- news_price_causality_aggregate

**news_price_causality_aggregate (AAPL):**

Table columns = candle/bar time resolution (declared time formats: 1D). Each cell states `news_return_corr`, `corr_p_value`, `sentiment_return_corr`, `news_volume_corr`, `sample_size`, `best_lag_minutes`, `best_lag_correlation`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1D |
|---|---|
| closed | not available (n=0) |
| london | not available (n=0) |
| ny_premarket | not available (n=0) |
| ny_regular | not available (n=0) |
| ny_afterhours | not available (n=0) |

## Status counts by time format
1D: analysis_at = 2026-08-09T14:00:14.881873+00:00: n=2 (of 2)
1D: angle = news_price_causality: n=2 (of 2)
1D: type = correlation: n=1 (of 2)
1D: type = lag: n=1 (of 2)
1D: quarter_key = 2023-Q1: n=2 (of 2)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/news_price_causality_aggregate`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/news_price_causality_aggregate/c646f8b883d4` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._