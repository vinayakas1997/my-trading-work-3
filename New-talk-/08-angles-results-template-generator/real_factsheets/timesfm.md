# timesfm (AAPL) -- TimesFM Time-Series Foundation Model

**timesfm (AAPL):** Zero-shot point + quantile forecast from Google's TimesFM foundation model (method 11 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/11-timesfm.md). General-purpose, not finance-specific — a comparison baseline alongside Chronos and Kronos, not a first-choice signal. Output: Point forecast plus all 9 real decile levels (q10 through q90 — the model's own trained quantile-head output, genuine model confidence, not a bolted-on statistical band) for the next 5 periods, plus context_length_used, model_backend ("pretrained" via google/timesfm-2.5-200m-pytorch, or "fallback_proxy" if the real checkpoint could not be loaded) and fallback_reason.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `context_length_used`, `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | context_length_used=147, last_close=149, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`context_length_used`, `last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | context_length_used=152.5, last_close=149.9, n=16, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| tuesday | not available | not available | not available | not available | not available | context_length_used=146.2, last_close=148.8, n=19, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| wednesday | not available | not available | not available | not available | not available | context_length_used=144.8, last_close=149.1, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| thursday | not available | not available | not available | not available | not available | context_length_used=145.8, last_close=149.1, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| friday | not available | not available | not available | not available | not available | context_length_used=146.8, last_close=148.3, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | context_length_used=148, last_close=148.1, n=23, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 2 | not available | not available | not available | not available | not available | context_length_used=144.5, last_close=149, n=21, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 3 | not available | not available | not available | not available | not available | context_length_used=148.5, last_close=151, n=19, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 4 | not available | not available | not available | not available | not available | context_length_used=145.1, last_close=149.2, n=23, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 5 | not available | not available | not available | not available | not available | context_length_used=151.9, last_close=146.7, n=9, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | context_length_used=101.5, last_close=142.6, n=4, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 6 | not available | not available | not available | not available | not available | context_length_used=114, last_close=137.1, n=21, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 7 | not available | not available | not available | not available | not available | context_length_used=134.5, last_close=147, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 8 | not available | not available | not available | not available | not available | context_length_used=156, last_close=163.8, n=23, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 9 | not available | not available | not available | not available | not available | context_length_used=178, last_close=150.2, n=21, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 10 | not available | not available | not available | not available | not available | context_length_used=191.5, last_close=140.8, n=6, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | context_length_used=112, last_close=138, n=25, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 3 | not available | not available | not available | not available | not available | context_length_used=156.5, last_close=154.1, n=64, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 4 | not available | not available | not available | not available | not available | context_length_used=191.5, last_close=140.8, n=6, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`q10`, `q20`, `q30`, `q40`, `q50`, `q60`, `q70`, `q80`, `q90`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | q10=143.1, q20=145.5, q30=147.1, q40=148.1, q50=149.1, q60=150.1, q70=151.2, q80=152.7, q90=154.9, actual_close=149, hit=0.9158, close_sq_error=10.1, close_abs_error=2.485, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 2 | not available | not available | not available | not available | not available | q10=141.7, q20=144.7, q30=146.4, q40=148, q50=149.2, q60=150.6, q70=152.2, q80=153.8, q90=156.5, actual_close=148.9, hit=0.8842, close_sq_error=20.76, close_abs_error=3.637, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 3 | not available | not available | not available | not available | not available | q10=140.3, q20=143.8, q30=146.1, q40=147.8, q50=149.3, q60=150.9, q70=152.6, q80=154.9, q90=158, actual_close=148.9, hit=0.8842, close_sq_error=29.04, close_abs_error=4.371, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 4 | not available | not available | not available | not available | not available | q10=139.2, q20=143.3, q30=145.9, q40=147.5, q50=149.5, q60=151.5, q70=153.1, q80=155.6, q90=159.5, actual_close=148.8, hit=0.8947, close_sq_error=38.48, close_abs_error=5.11, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 5 | not available | not available | not available | not available | not available | q10=138.3, q20=142.8, q30=145.5, q40=147.5, q50=149.6, q60=151.7, q70=153.9, q80=156.5, q90=160.6, actual_close=148.7, hit=0.9053, close_sq_error=45, close_abs_error=5.582, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = pretrained: n=95 (of 95)
1D: checkpoint = google/timesfm-2.5-200m-pytorch: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/timesfm`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/timesfm/ba89ad03e587` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._