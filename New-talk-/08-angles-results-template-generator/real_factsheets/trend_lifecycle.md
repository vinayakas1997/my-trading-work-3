# trend_lifecycle (AAPL) -- Trend Lifecycle

**trend_lifecycle (AAPL):** Peak/trough pattern library, KNN similarity matching, trend stage classification, reversal signals with percentage exit thresholds Output: Angle-specific results

Real data covers 2022-03-29 to 2022-08-17 (141 days), 3 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D, 1W). Each cell states `stated_confidence`, `suggested_exit_pct`, `actual_subsequent_drawdown_pct`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D | 1W |
|---|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | not available (n=0) | not available |
| london | not available | not available | not available | not available | not available | not available (n=0) | not available |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) | not available |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) | not available |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) | not available |

## Breakdown by calendar tag

Same fields as the session table above (`stated_confidence`, `suggested_exit_pct`, `actual_subsequent_drawdown_pct`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D | 1W |
|---|---|---|---|---|---|---|---|
| tuesday | not available | not available | not available | not available | not available | stated_confidence=0, suggested_exit_pct=nan, actual_subsequent_drawdown_pct=-0.2779, n=1, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |
| wednesday | not available | not available | not available | not available | not available | stated_confidence=0.35, suggested_exit_pct=-0.1, actual_subsequent_drawdown_pct=-0.2394, n=2, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D | 1W |
|---|---|---|---|---|---|---|---|
| 3 | not available | not available | not available | not available | not available | stated_confidence=0.35, suggested_exit_pct=-0.1, actual_subsequent_drawdown_pct=-0.2394, n=2, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |
| 5 | not available | not available | not available | not available | not available | stated_confidence=0, suggested_exit_pct=nan, actual_subsequent_drawdown_pct=-0.2779, n=1, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D | 1W |
|---|---|---|---|---|---|---|---|
| 3 | not available | not available | not available | not available | not available | stated_confidence=0, suggested_exit_pct=nan, actual_subsequent_drawdown_pct=-0.2779, n=1, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |
| 8 | not available | not available | not available | not available | not available | stated_confidence=0.35, suggested_exit_pct=-0.1, actual_subsequent_drawdown_pct=-0.2394, n=2, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D | 1W |
|---|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | stated_confidence=0, suggested_exit_pct=nan, actual_subsequent_drawdown_pct=-0.2779, n=1, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |
| 3 | not available | not available | not available | not available | not available | stated_confidence=0.35, suggested_exit_pct=-0.1, actual_subsequent_drawdown_pct=-0.2394, n=2, computed_at=2026-08-09T13:29:48.572451+00:00, run_id=7e00e13e1985 | not available |

## Status counts by time format
1D: signal_type = insufficient_data: n=1 (of 3)
1D: signal_type = book_profits: n=1 (of 3)
1D: signal_type = re_entry: n=1 (of 3)
1D: lifecycle_stage = downtrend: n=2 (of 3)
1D: lifecycle_stage = sideways: n=1 (of 3)
1D: outcome_mature = False: n=2 (of 3)
1D: outcome_mature = True: n=1 (of 3)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/trend_lifecycle`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/trend_lifecycle/7e00e13e1985` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._