# Angle results summary -- AAPL

One section per angle, in a fixed order. No comparison or ranking across sections is implied by that order.

---

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

---

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

---

# peer_relative_strength (AAPL) -- Peer Relative Strength

**peer_relative_strength (AAPL):** Measures how a symbol performs relative to its watchlist peer basket over time using rolling correlation and relative (excess) returns. Stands apart from shock_clustering (which only answers "which symbols shock together on shock dates") by computing peer co-movement and relative strength as a continuous, windowed signal across the full requested range. Output: Rolling peer correlation and excess-return rows per sampled bar: date, peer_symbol, correlation (63-day rolling), relative_return_20d.

Real data covers 2023-02-02 to 2023-05-15 (102 days), 30 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `correlation`, `relative_return_20d`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | not available (n=0) |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`correlation`, `relative_return_20d`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | correlation=0.06155, relative_return_20d=0.01625, n=12, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| thursday | not available | not available | not available | not available | not available | correlation=0.3967, relative_return_20d=-0.08707, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| friday | not available | not available | not available | not available | not available | correlation=0.3019, relative_return_20d=0.03601, n=12, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.2603, relative_return_20d=0.02135, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 2 | not available | not available | not available | not available | not available | correlation=0.2113, relative_return_20d=-0.004831, n=8, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 3 | not available | not available | not available | not available | not available | correlation=0.1805, relative_return_20d=-0.001959, n=8, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 4 | not available | not available | not available | not available | not available | correlation=0.2577, relative_return_20d=0.01599, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 5 | not available | not available | not available | not available | not available | correlation=0.2499, relative_return_20d=-0.03248, n=2, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | correlation=0.3863, relative_return_20d=-0.06845, n=8, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 3 | not available | not available | not available | not available | not available | correlation=0.2913, relative_return_20d=0.04574, n=10, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 4 | not available | not available | not available | not available | not available | correlation=0.1636, relative_return_20d=-0.03462, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 5 | not available | not available | not available | not available | not available | correlation=-0.04054, relative_return_20d=0.06712, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.3335, relative_return_20d=-0.005015, n=18, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 2 | not available | not available | not available | not available | not available | correlation=0.06155, relative_return_20d=0.01625, n=12, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

## Status counts by time format
1D: analysis_at = 2026-08-09T14:00:17.871939+00:00: n=30 (of 30)
1D: angle = peer_relative_strength: n=30 (of 30)
1D: date = 2023-02-02: n=2 (of 30)
1D: date = 2023-02-09: n=2 (of 30)
1D: date = 2023-02-16: n=2 (of 30)
1D: date = 2023-02-24: n=2 (of 30)
1D: date = 2023-03-03: n=2 (of 30)
1D: date = 2023-03-10: n=2 (of 30)
1D: date = 2023-03-17: n=2 (of 30)
1D: date = 2023-03-24: n=2 (of 30)
1D: date = 2023-03-31: n=2 (of 30)
1D: date = 2023-04-10: n=2 (of 30)
1D: date = 2023-04-17: n=2 (of 30)
1D: date = 2023-04-24: n=2 (of 30)
1D: date = 2023-05-01: n=2 (of 30)
1D: date = 2023-05-08: n=2 (of 30)
1D: date = 2023-05-15: n=2 (of 30)
1D: peer_symbol = JNJ: n=15 (of 30)
1D: peer_symbol = TSLA: n=15 (of 30)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/peer_relative_strength`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/peer_relative_strength/026004a67db0` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# peer_relative_strength_forward_validation (AAPL) -- peer_relative_strength_forward_validation

**peer_relative_strength_forward_validation (AAPL):**

Table columns = candle/bar time resolution (declared time formats: 1D). Each cell states `n_rows`, `forward_5d_corr`, `forward_5d_p_value`, `forward_5d_ci_lower`, `forward_5d_ci_upper`, `forward_5d_sample_size`, `forward_10d_corr`, `forward_10d_p_value`, `forward_10d_ci_lower`, `forward_10d_ci_upper`, `forward_10d_sample_size`, `forward_20d_corr`, `forward_20d_p_value`, `forward_20d_ci_lower`, `forward_20d_ci_upper`, `forward_20d_sample_size`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

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
1D: peer_symbol = JNJ: n=2 (of 4)
1D: peer_symbol = TSLA: n=2 (of 4)
1D: quarter_key = 2023-Q1: n=2 (of 4)
1D: quarter_key = 2023-Q2: n=2 (of 4)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/peer_relative_strength_forward_validation`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/peer_relative_strength_forward_validation/e5752e9e5cde` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# pnl_attribution (AAPL) -- PnL Attribution

**pnl_attribution (AAPL):** Realized-trade PnL statistics per symbol -- win rate, average win/loss, trade count -- computed from Phase 6 (vinu-live) execution logs. Every field includes sample size and confidence interval. Deviates from the standard runner-driven angle pattern: its natural input is closed positions/fills, not price bars, so it is push-fed via POST /pnl-attribution/{symbol}/record (Phase 7's feedback loop) rather than pulled by AngleRunner from bars/news. `compute()` still exists with the standard signature so a generic `/run/{ticker}` sweep doesn't error, but it is a documented no-op there -- real population happens through the ingest path (`pnl_attribution_ingest.py`), which calls `aggregate_pnl_attribution` directly and writes via `AngleStorage.write()`. Output: PnL attribution results with confidence intervals

## Status counts by time format
1D: analysis_at = 2026-08-09T14:00:23.819131+00:00: n=1 (of 1)
1D: angle = pnl_attribution: n=1 (of 1)
1D: status = no_data: n=1 (of 1)
1D: closed_positions_json = []: n=1 (of 1)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/pnl_attribution`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/pnl_attribution/fb10e1ec51b3` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---
