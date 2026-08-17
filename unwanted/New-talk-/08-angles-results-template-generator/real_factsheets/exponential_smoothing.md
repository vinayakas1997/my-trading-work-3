# exponential_smoothing (AAPL) -- Exponential Smoothing Classical Baseline

**exponential_smoothing (AAPL):** Double exponential smoothing (Holt's linear trend method) forecast — the classical, essentially-free statistical baseline (method 28 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/28-exponential-smoothing.md). Weights recent close-price observations more heavily than older ones via an exponentially-decaying scheme, fitting a level + trend decomposition (no seasonal component — daily-bar equity series have no reliable fixed seasonal period) and reporting the one-step-ahead point forecast alongside the fitted level/trend components. Output: One-step-ahead point forecast, fitted smoothing parameters (alpha, beta), and level/trend decomposition

Condition: N=100 candles of history considered before each forecast ("100 candles" means 100 candles at that column's own resolution -- 100 one-minute candles for the `1min` column, 100 daily candles for the `1D` column, not a fixed time window applied to every column).

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `forecast`, `alpha`, `beta`, `level`, `trend`, `sse`, `actual_price`, `hit`, `abs_error`, `squared_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=100, forecast=148.5, alpha=0.9281, beta=0.004747, level=148.5, trend=-0.05969, sse=1159, actual_price=148.6, hit=0.4242, abs_error=2.532, squared_error=10.25, n=99, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `forecast`, `alpha`, `beta`, `level`, `trend`, `sse`, `actual_price`, `hit`, `abs_error`, `squared_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=100, forecast=149.9, alpha=0.9276, beta=0.004877, level=150, trend=-0.04072, sse=1158, actual_price=149.6, hit=0.3125, abs_error=2.319, squared_error=9.575, n=16, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| tuesday | not available | not available | not available | not available | not available | n_observations=100, forecast=148.1, alpha=0.9314, beta=0.002189, level=148.2, trend=-0.0954, sse=1161, actual_price=149, hit=0.6, abs_error=1.645, squared_error=5.337, n=20, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| wednesday | not available | not available | not available | not available | not available | n_observations=100, forecast=148.3, alpha=0.9268, beta=0.003689, level=148.4, trend=-0.07712, sse=1154, actual_price=148.7, hit=0.4286, abs_error=2.942, squared_error=12.89, n=21, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| thursday | not available | not available | not available | not available | not available | n_observations=100, forecast=148.6, alpha=0.9261, beta=0.00752, level=148.7, trend=-0.02452, sse=1159, actual_price=147.7, hit=0.3333, abs_error=3.178, squared_error=13.33, n=21, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| friday | not available | not available | not available | not available | not available | n_observations=100, forecast=147.7, alpha=0.9284, beta=0.005371, level=147.8, trend=-0.05789, sse=1162, actual_price=148, hit=0.4286, abs_error=2.481, squared_error=9.743, n=21, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=100, forecast=148, alpha=0.9484, beta=0.003161, level=148.1, trend=-0.07719, sse=1150, actual_price=148.3, hit=0.3043, abs_error=2.03, squared_error=6.77, n=23, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 2 | not available | not available | not available | not available | not available | n_observations=100, forecast=147, alpha=0.9393, beta=0.001487, level=147.1, trend=-0.08381, sse=1140, actual_price=147, hit=0.48, abs_error=2.913, squared_error=13.23, n=25, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 3 | not available | not available | not available | not available | not available | n_observations=100, forecast=151.1, alpha=0.8934, beta=0.01166, level=151, trend=0.08991, sse=1189, actual_price=150.9, hit=0.4737, abs_error=2.424, squared_error=8.362, n=19, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 4 | not available | not available | not available | not available | not available | n_observations=100, forecast=149.1, alpha=0.9198, beta=0.006028, level=149.2, trend=-0.1009, sse=1162, actual_price=149.4, hit=0.4348, abs_error=2.874, squared_error=13.44, n=23, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 5 | not available | not available | not available | not available | not available | n_observations=100, forecast=146.6, alpha=0.9392, beta=0, level=146.8, trend=-0.1586, sse=1165, actual_price=146.2, hit=0.4444, abs_error=2.106, squared_error=6.734, n=9, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=100, forecast=142.3, alpha=0.9894, beta=0, level=142.6, trend=-0.3092, sse=1134, actual_price=144.8, hit=0.5, abs_error=2.816, squared_error=14.89, n=4, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 6 | not available | not available | not available | not available | not available | n_observations=100, forecast=136.8, alpha=0.9632, beta=0, level=137.1, trend=-0.2895, sse=1201, actual_price=136.6, hit=0.4762, abs_error=2.806, squared_error=10.83, n=21, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 7 | not available | not available | not available | not available | not available | n_observations=100, forecast=146.7, alpha=0.9203, beta=0, level=146.8, trend=-0.1655, sse=1209, actual_price=148.1, hit=0.4, abs_error=2.31, squared_error=8.425, n=20, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 8 | not available | not available | not available | not available | not available | n_observations=100, forecast=164.2, alpha=0.8683, beta=0.02043, level=163.9, trend=0.2838, sse=1173, actual_price=163.7, hit=0.4783, abs_error=2.074, squared_error=7.897, n=23, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 9 | not available | not available | not available | not available | not available | n_observations=100, forecast=150.2, alpha=0.9204, beta=0, level=150.3, trend=-0.08175, sse=1141, actual_price=149.5, hit=0.4762, abs_error=2.923, squared_error=13.58, n=21, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 10 | not available | not available | not available | not available | not available | n_observations=100, forecast=139.3, alpha=0.9985, beta=0, level=139.3, trend=-0.009248, sse=985.6, actual_price=139.3, hit=0.1, abs_error=2.514, squared_error=9.275, n=10, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=100, forecast=137.6, alpha=0.9674, beta=0, level=137.9, trend=-0.2926, sse=1190, actual_price=137.9, hit=0.48, abs_error=2.808, squared_error=11.48, n=25, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 3 | not available | not available | not available | not available | not available | n_observations=100, forecast=154.1, alpha=0.9017, beta=0.007343, level=154.1, trend=0.02341, sse=1174, actual_price=154.2, hit=0.4531, abs_error=2.426, squared_error=9.928, n=64, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |
| 4 | not available | not available | not available | not available | not available | n_observations=100, forecast=139.3, alpha=0.9985, beta=0, level=139.3, trend=-0.009248, sse=985.6, actual_price=139.3, hit=0.1, abs_error=2.514, squared_error=9.275, n=10, computed_at=2026-08-09T13:29:48.180462+00:00, run_id=4b5a6ac09343 |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: predicted_direction = down: n=60 (of 99)
1D: predicted_direction = up: n=32 (of 99)
1D: predicted_direction = flat: n=7 (of 99)
1D: actual_direction = down: n=50 (of 99)
1D: actual_direction = up: n=48 (of 99)
1D: actual_direction = flat: n=1 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/exponential_smoothing`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/exponential_smoothing/4b5a6ac09343` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._