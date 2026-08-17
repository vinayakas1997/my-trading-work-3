# moirai (AAPL) -- MOIRAI Any-Variate Time-Series Foundation Model (fallback proxy)

**moirai (AAPL):** Forecast in the spirit of Salesforce's MOIRAI (method 13 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/13-moirai.md). The real `uni2ts` package exists but would downgrade the shared environment's torch build and can't exercise MOIRAI's any-variate multi-ticker mechanism from this per-symbol interface anyway — this angle uses an honestly-labeled AR(3) statistical fallback proxy. See compute.py's module docstring. Output: Point + p10/p90 forecast for the next 5 periods, plus model_backend (always "fallback_proxy"), fallback_reason, and any_variate_note explaining the single-ticker degeneration.

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
| closed | not available | not available | not available | not available | not available | last_close=149, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=149.9, n=16, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| tuesday | not available | not available | not available | not available | not available | last_close=148.8, n=19, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| wednesday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| thursday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| friday | not available | not available | not available | not available | not available | last_close=148.3, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=148.1, n=23, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 2 | not available | not available | not available | not available | not available | last_close=149, n=21, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 3 | not available | not available | not available | not available | not available | last_close=151, n=19, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 4 | not available | not available | not available | not available | not available | last_close=149.2, n=23, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 5 | not available | not available | not available | not available | not available | last_close=146.7, n=9, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | last_close=142.6, n=4, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 6 | not available | not available | not available | not available | not available | last_close=137.1, n=21, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 7 | not available | not available | not available | not available | not available | last_close=147, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 8 | not available | not available | not available | not available | not available | last_close=163.8, n=23, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 9 | not available | not available | not available | not available | not available | last_close=150.2, n=21, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 10 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | last_close=138, n=25, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 3 | not available | not available | not available | not available | not available | last_close=154.1, n=64, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 4 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`point`, `p10`, `p90`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | point=149, p10=144.9, p90=153.1, actual_close=149, hit=0.8105, close_sq_error=9.612, close_abs_error=2.419, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 2 | not available | not available | not available | not available | not available | point=149, p10=143.2, p90=154.8, actual_close=148.9, hit=0.8316, close_sq_error=20.1, close_abs_error=3.592, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 3 | not available | not available | not available | not available | not available | point=149, p10=141.9, p90=156.1, actual_close=148.9, hit=0.8316, close_sq_error=27.36, close_abs_error=4.266, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 4 | not available | not available | not available | not available | not available | point=149, p10=140.8, p90=157.2, actual_close=148.8, hit=0.7895, close_sq_error=34.83, close_abs_error=4.851, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 5 | not available | not available | not available | not available | not available | point=149, p10=139.9, p90=158.1, actual_close=148.7, hit=0.8632, close_sq_error=40.9, close_abs_error=5.327, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = fallback_proxy: n=95 (of 95)
1D: fallback_reason = uni2ts (real MOIRAI package) would downgrade the shared environment's torch 2.13.0+cpu to torch==2.4.1 plus pull in jax/lightning — too risky to install for one angle; additionally this angle's per-symbol compute() call can't exercise MOIRAI's any-variate multi-ticker mechanism anyway, so a single-series AR(3) statistical proxy is used instead, explicitly labeled as the any-variate-degenerate case.: n=95 (of 95)
1D: any_variate_note = This call is single-ticker only (compute() receives one symbol's bars at a time) — MOIRAI's any-variate joint-multi-series mechanism is not exercised; this is the single-variate degenerate case.: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/moirai`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/moirai/b58d6015fed8` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._