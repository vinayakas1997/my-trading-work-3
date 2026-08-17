# moment (AAPL) -- MOMENT Multi-Task Time-Series Foundation Model (fallback proxy)

**moment (AAPL):** Forecast in the spirit of MOMENT's forecasting task (method 14 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/14-moment.md). The real `momentfm` package failed to build in this Python 3.12 environment (pkgutil.ImpImporter incompatibility, confirmed via an actual install attempt) — this angle uses an honestly-labeled statistical fallback proxy for the forecasting task only. See compute.py's module docstring. Output: Point + p10/p90 forecast for the next 5 periods, plus model_backend (always "fallback_proxy"), fallback_reason, and task_note flagging that only the forecasting task is implemented.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | last_close=149, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=149.9, n=16, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| tuesday | not available | not available | not available | not available | not available | last_close=148.8, n=19, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| wednesday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| thursday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| friday | not available | not available | not available | not available | not available | last_close=148.3, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=148.1, n=23, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 2 | not available | not available | not available | not available | not available | last_close=149, n=21, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 3 | not available | not available | not available | not available | not available | last_close=151, n=19, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 4 | not available | not available | not available | not available | not available | last_close=149.2, n=23, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 5 | not available | not available | not available | not available | not available | last_close=146.7, n=9, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | last_close=142.6, n=4, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 6 | not available | not available | not available | not available | not available | last_close=137.1, n=21, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 7 | not available | not available | not available | not available | not available | last_close=147, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 8 | not available | not available | not available | not available | not available | last_close=163.8, n=23, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 9 | not available | not available | not available | not available | not available | last_close=150.2, n=21, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 10 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | last_close=138, n=25, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 3 | not available | not available | not available | not available | not available | last_close=154.1, n=64, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 4 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`point`, `p10`, `p90`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | point=149.1, p10=145, p90=153.2, actual_close=149, hit=0.8, close_sq_error=9.797, close_abs_error=2.533, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 2 | not available | not available | not available | not available | not available | point=149.1, p10=143.3, p90=154.9, actual_close=148.9, hit=0.8316, close_sq_error=21.11, close_abs_error=3.597, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 3 | not available | not available | not available | not available | not available | point=149.2, p10=142.1, p90=156.3, actual_close=148.9, hit=0.7789, close_sq_error=29.68, close_abs_error=4.189, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 4 | not available | not available | not available | not available | not available | point=149.2, p10=141, p90=157.4, actual_close=148.8, hit=0.8105, close_sq_error=37.96, close_abs_error=4.91, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 5 | not available | not available | not available | not available | not available | point=149.3, p10=140.1, p90=158.5, actual_close=148.7, hit=0.8, close_sq_error=44.12, close_abs_error=5.281, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = fallback_proxy: n=95 (of 95)
1D: fallback_reason = momentfm (real MOMENT package) failed to build in this environment: "AttributeError: module 'pkgutil' has no attribute 'ImpImporter'" — a genuine Python 3.12 incompatibility in one of its transitive build dependencies, confirmed via `pip install momentfm`. Using a statistical fallback proxy for the forecasting task only; MOMENT's embeddings/anomaly-detection/imputation tasks are not implemented.: n=95 (of 95)
1D: task_note = forecasting task only — embeddings/anomaly_detection/imputation not implemented: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/moment`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/moment/099bed1d7c60` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._