# news_price_causality_impact (AAPL) -- news_price_causality_impact

**news_price_causality_impact (AAPL):**

Table columns = candle/bar time resolution (declared time formats: 1D). Each cell states `ticker_count`, `ts`, `sentiment_score`, `abnormal_return_30m`, `car_1h`, `ar_p_value`, `computed_at`, `novelty_score`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1D |
|---|---|
| closed | ticker_count=2.022, ts=1.674e+09, sentiment_score=0.9556, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9343, n=45, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| london | ticker_count=1.93, ts=1.674e+09, sentiment_score=0.6279, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9187, n=43, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| ny_premarket | ticker_count=2.238, ts=1.674e+09, sentiment_score=1.524, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9438, n=21, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| ny_regular | ticker_count=2.163, ts=1.674e+09, sentiment_score=0.3023, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.8805, n=43, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| ny_afterhours | ticker_count=1.4, ts=1.674e+09, sentiment_score=1.2, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9735, n=5, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |

## Breakdown by calendar tag

Same fields as the session table above (`ticker_count`, `ts`, `sentiment_score`, `abnormal_return_30m`, `car_1h`, `ar_p_value`, `computed_at`, `novelty_score`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1D |
|---|---|
| monday | ticker_count=1.966, ts=1.675e+09, sentiment_score=1.103, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9456, n=29, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| tuesday | ticker_count=2.125, ts=1.674e+09, sentiment_score=1.312, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9219, n=32, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| wednesday | ticker_count=1.645, ts=1.674e+09, sentiment_score=1.129, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9389, n=31, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| thursday | ticker_count=2.2, ts=1.674e+09, sentiment_score=0.1333, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9015, n=30, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| friday | ticker_count=2.417, ts=1.674e+09, sentiment_score=0.4583, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.8593, n=24, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| saturday | ticker_count=1.667, ts=1.674e+09, sentiment_score=-0.3333, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9414, n=3, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| sunday | ticker_count=2, ts=1.675e+09, sentiment_score=-0.25, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9467, n=8, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1D |
|---|---|
| 2 | ticker_count=2.167, ts=1.673e+09, sentiment_score=0.5833, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9323, n=36, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| 3 | ticker_count=2.346, ts=1.674e+09, sentiment_score=0.8462, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9037, n=52, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| 4 | ticker_count=1.711, ts=1.675e+09, sentiment_score=0.7333, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9161, n=45, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |
| 5 | ticker_count=1.833, ts=1.675e+09, sentiment_score=0.9583, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9298, n=24, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |

### month (real calendar month number, 1-12)

| month | 1D |
|---|---|
| 1 | ticker_count=2.045, ts=1.674e+09, sentiment_score=0.7707, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9178, n=157, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |

### quarter (real calendar quarter, 1-4)

| quarter | 1D |
|---|---|
| 1 | ticker_count=2.045, ts=1.674e+09, sentiment_score=0.7707, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9178, n=157, computed_at=2026-08-09T14:00:23.829303+00:00, run_id=118020ea97b3 |

## Status counts by time format
1D: type = impact: n=157 (of 157)
1D: is_primary = True: n=100 (of 157)
1D: is_primary = False: n=57 (of 157)
1D: sentiment = NEUTRAL: n=76 (of 157)
1D: sentiment = BULLISH: n=61 (of 157)
1D: sentiment = BEARISH: n=20 (of 157)
1D: impact_label = low: n=157 (of 157)
1D: ar_significant = False: n=157 (of 157)
1D: ar_model = none: n=157 (of 157)
1D: analysis_at = 2026-08-09T14:00:14.667975+00:00: n=157 (of 157)
1D: angle = news_price_causality: n=157 (of 157)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/news_price_causality_impact`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/news_price_causality_impact/118020ea97b3` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._