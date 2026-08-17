# kalman_filters (AAPL) -- Kalman Filter State Estimation

**kalman_filters (AAPL):** Classical recursive state-estimation baseline (method 27 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/27-kalman-filters.md). Recursively estimates a hidden underlying price level and local trend from noisy close-price observations via a predict-then-correct cycle (statsmodels' local-linear-trend structural time series model — a two-state Kalman filter/smoother). Reports the present/recent filtered and smoothed state plus its uncertainty (state covariance) — not a forward forecast. Output: Filtered and smoothed level/trend state estimates plus their standard deviations (state covariance uncertainty)

Condition: N=100 candles of history considered before each forecast ("100 candles" means 100 candles at that column's own resolution -- 100 one-minute candles for the `1min` column, 100 daily candles for the `1D` column, not a fixed time window applied to every column).

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `filtered_level`, `filtered_level_std`, `filtered_trend`, `filtered_trend_std`, `actual_price`, `hit`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=100, filtered_level=148.5, filtered_level_std=0.7566, filtered_trend=-0.04095, filtered_trend_std=0.4907, actual_price=148.6, hit=0.4444, n=99, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `filtered_level`, `filtered_level_std`, `filtered_trend`, `filtered_trend_std`, `actual_price`, `hit`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=100, filtered_level=150, filtered_level_std=0.7748, filtered_trend=-0.00459, filtered_trend_std=0.4886, actual_price=149.6, hit=0.25, n=16, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| tuesday | not available | not available | not available | not available | not available | n_observations=100, filtered_level=148.2, filtered_level_std=0.7319, filtered_trend=-0.07534, filtered_trend_std=0.4648, actual_price=149, hit=0.65, n=20, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| wednesday | not available | not available | not available | not available | not available | n_observations=100, filtered_level=148.4, filtered_level_std=0.7313, filtered_trend=-0.02042, filtered_trend_std=0.4487, actual_price=148.7, hit=0.4286, n=21, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| thursday | not available | not available | not available | not available | not available | n_observations=100, filtered_level=148.7, filtered_level_std=0.7469, filtered_trend=0.001008, filtered_trend_std=0.4883, actual_price=147.7, hit=0.4762, n=21, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| friday | not available | not available | not available | not available | not available | n_observations=100, filtered_level=147.7, filtered_level_std=0.8011, filtered_trend=-0.09838, filtered_trend_std=0.5612, actual_price=148, hit=0.381, n=21, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=148.1, filtered_level_std=0.6133, filtered_trend=-0.01183, filtered_trend_std=0.4739, actual_price=148.3, hit=0.3913, n=23, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 2 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=147.1, filtered_level_std=0.6541, filtered_trend=-0.05707, filtered_trend_std=0.5073, actual_price=147, hit=0.48, n=25, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 3 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=150.9, filtered_level_std=1.001, filtered_trend=0.05425, filtered_trend_std=0.5152, actual_price=150.9, hit=0.4737, n=19, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 4 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=149.3, filtered_level_std=0.8251, filtered_trend=-0.07235, filtered_trend_std=0.447, actual_price=149.4, hit=0.4348, n=23, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 5 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=146.8, filtered_level_std=0.716, filtered_trend=-0.1913, filtered_trend_std=0.5471, actual_price=146.2, hit=0.4444, n=9, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=142.6, filtered_level_std=0.07884, filtered_trend=-0.3092, filtered_trend_std=0.3412, actual_price=144.8, hit=0.5, n=4, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 6 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=137, filtered_level_std=0.4981, filtered_trend=-0.3406, filtered_trend_std=0.4134, actual_price=136.6, hit=0.4762, n=21, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 7 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=146.9, filtered_level_std=0.8804, filtered_trend=-0.1043, filtered_trend_std=0.3659, actual_price=148.1, hit=0.3, n=20, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 8 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=164, filtered_level_std=1.189, filtered_trend=0.5452, filtered_trend_std=0.6506, actual_price=163.7, hit=0.3913, n=23, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 9 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=150.3, filtered_level_std=0.9021, filtered_trend=-0.1836, filtered_trend_std=0.5532, actual_price=149.5, hit=0.5238, n=21, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 10 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=139.3, filtered_level_std=0.02169, filtered_trend=-0.2264, filtered_trend_std=0.4633, actual_price=139.3, hit=0.6, n=10, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=137.9, filtered_level_std=0.431, filtered_trend=-0.3356, filtered_trend_std=0.4018, actual_price=137.9, hit=0.48, n=25, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 3 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=154.1, filtered_level_std=0.9985, filtered_trend=0.1031, filtered_trend_std=0.5297, actual_price=154.2, hit=0.4062, n=64, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |
| 4 | not available | not available | not available | not available | not available | n_observations=100, filtered_level=139.3, filtered_level_std=0.02169, filtered_trend=-0.2264, filtered_trend_std=0.4633, actual_price=139.3, hit=0.6, n=10, computed_at=2026-08-09T13:29:48.148526+00:00, run_id=f2ead521b583 |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: predicted_direction = down: n=74 (of 99)
1D: predicted_direction = up: n=25 (of 99)
1D: actual_direction = down: n=50 (of 99)
1D: actual_direction = up: n=48 (of 99)
1D: actual_direction = flat: n=1 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/kalman_filters`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/kalman_filters/f2ead521b583` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._