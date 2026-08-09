# regime_analysis (AAPL) -- Regime Analysis

**regime_analysis (AAPL):** 4-regime classifier (bull/bear/high_vol/sideways), transition matrix, per-regime Sharpe ratio Output: Angle-specific results

Real data covers 2022-07-26 to 2022-10-17 (83 days), 59 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D, 1W, 1M). Each cell states `ret_20d`, `vol_21d`, `vol_trailing_z`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M |
|---|---|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | not available (n=0) | not available | not available |
| london | not available | not available | not available | not available | not available | not available (n=0) | not available | not available |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) | not available | not available |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) | not available | not available |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) | not available | not available |

## Breakdown by calendar tag

Same fields as the session table above (`ret_20d`, `vol_21d`, `vol_trailing_z`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M |
|---|---|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | ret_20d=0.004544, vol_21d=0.3209, vol_trailing_z=-0.3368, n=11, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| tuesday | not available | not available | not available | not available | not available | ret_20d=0.01095, vol_21d=0.3028, vol_trailing_z=-0.5476, n=12, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| wednesday | not available | not available | not available | not available | not available | ret_20d=0.01365, vol_21d=0.3011, vol_trailing_z=-0.57, n=12, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| thursday | not available | not available | not available | not available | not available | ret_20d=0.003601, vol_21d=0.3033, vol_trailing_z=-0.5457, n=12, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| friday | not available | not available | not available | not available | not available | ret_20d=-0.008643, vol_21d=0.305, vol_trailing_z=-0.5263, n=12, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M |
|---|---|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | ret_20d=0.008707, vol_21d=0.3112, vol_trailing_z=-0.4552, n=14, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 2 | not available | not available | not available | not available | not available | ret_20d=-0.01246, vol_21d=0.3086, vol_trailing_z=-0.49, n=15, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 3 | not available | not available | not available | not available | not available | ret_20d=0.01187, vol_21d=0.312, vol_trailing_z=-0.4286, n=11, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 4 | not available | not available | not available | not available | not available | ret_20d=0.02375, vol_21d=0.2969, vol_trailing_z=-0.6128, n=13, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 5 | not available | not available | not available | not available | not available | ret_20d=-0.01493, vol_21d=0.3002, vol_trailing_z=-0.5957, n=6, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M |
|---|---|---|---|---|---|---|---|---|
| 7 | not available | not available | not available | not available | not available | ret_20d=0.1426, vol_21d=0.2644, vol_trailing_z=-0.9768, n=4, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 8 | not available | not available | not available | not available | not available | ret_20d=0.1053, vol_21d=0.2795, vol_trailing_z=-0.8371, n=23, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 9 | not available | not available | not available | not available | not available | ret_20d=-0.08421, vol_21d=0.305, vol_trailing_z=-0.498, n=21, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 10 | not available | not available | not available | not available | not available | ret_20d=-0.08545, vol_21d=0.3808, vol_trailing_z=0.3308, n=11, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M |
|---|---|---|---|---|---|---|---|---|
| 3 | not available | not available | not available | not available | not available | ret_20d=0.02551, vol_21d=0.2894, vol_trailing_z=-0.7004, n=48, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |
| 4 | not available | not available | not available | not available | not available | ret_20d=-0.08545, vol_21d=0.3808, vol_trailing_z=0.3308, n=11, computed_at=2026-08-09T13:29:48.468337+00:00, run_id=927f4a90aef3 | not available | not available |

## Status counts by time format
1D: regime = bear: n=33 (of 59)
1D: regime = bull: n=23 (of 59)
1D: regime = sideways: n=3 (of 59)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/regime_analysis`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/regime_analysis/927f4a90aef3` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._