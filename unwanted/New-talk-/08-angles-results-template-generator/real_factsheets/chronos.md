# chronos (AAPL) -- Chronos Time-Series Foundation Model

**chronos (AAPL):** Zero-shot probabilistic forecast from Amazon's Chronos-T5 time-series foundation model (method 10 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/10-chronos.md). General-purpose, not finance-specific — a comparison baseline against Kronos, not a first-choice signal (per the spec's own caveat that general TSFMs tend to underperform finance-specific models on K-line data). Output: Quantile forecast (p10/median/p90) for the next 5 periods, plus model_backend ("pretrained" via amazon/chronos-t5-large, or "fallback_proxy" if the real pipeline could not be loaded).

Real data covers 2024-01-17 to 2024-03-19 (62 days), 44 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | last_close=180.7, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=181, n=8, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| tuesday | not available | not available | not available | not available | not available | last_close=180.5, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| wednesday | not available | not available | not available | not available | not available | last_close=180.1, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| thursday | not available | not available | not available | not available | not available | last_close=181.1, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| friday | not available | not available | not available | not available | not available | last_close=181, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=178.1, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 2 | not available | not available | not available | not available | not available | last_close=177.5, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 3 | not available | not available | not available | not available | not available | last_close=179.7, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 4 | not available | not available | not available | not available | not available | last_close=186.2, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 5 | not available | not available | not available | not available | not available | last_close=184.5, n=4, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=188.6, n=11, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 2 | not available | not available | not available | not available | not available | last_close=182.7, n=20, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 3 | not available | not available | not available | not available | not available | last_close=171.1, n=13, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=180.7, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`p10`, `median`, `p90`, `actual`, `hit`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | p10=177.9, median=180.8, p90=183.7, actual=180.6, hit=0.8864, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 2 | not available | not available | not available | not available | not available | p10=176.6, median=181, p90=185, actual=180.3, hit=0.7955, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 3 | not available | not available | not available | not available | not available | p10=175.6, median=181.2, p90=186.1, actual=179.8, hit=0.7273, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 4 | not available | not available | not available | not available | not available | p10=174.7, median=181.4, p90=187, actual=179.3, hit=0.75, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 5 | not available | not available | not available | not available | not available | p10=173.9, median=181.4, p90=188, actual=178.8, hit=0.6818, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

## Status counts by time format
1D: status = ok: n=44 (of 44)
1D: model_backend = pretrained: n=44 (of 44)
1D: checkpoint = amazon/chronos-t5-large: n=44 (of 44)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/chronos`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/chronos/3951acb61e1c` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._