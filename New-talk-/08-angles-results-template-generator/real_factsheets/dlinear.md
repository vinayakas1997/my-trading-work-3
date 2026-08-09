# dlinear (AAPL) -- DLinear Decomposition Linear Forecast

**dlinear (AAPL):** Trained-from-scratch DLinear model (method 18 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/18-dlinear.md) — the simplest of six architectures the source survey found "actually win on finance". Decomposes the close-price window into a moving-average trend and a seasonal residual, fits one small linear layer to each on a handful of Adam epochs at request time, and sums their outputs into a one-step-ahead point forecast, thresholded to a direction. Output: One-step-ahead forecast price/return, thresholded direction (up/down/flat), and the fit's training-window count and final training loss.

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=149, n_train_windows=119, lookback=30, last_close=148.5, forecast_price=148.6, forecast_return=0.0005069, train_loss=0.1057, actual_price=148.6, actual_return=0.0004276, hit=0.5152, n=99, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=152.5, n_train_windows=122.5, lookback=30, last_close=149.9, forecast_price=150.9, forecast_return=0.007025, train_loss=0.1053, actual_price=149.6, actual_return=-0.001817, hit=0.375, n=16, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| tuesday | not available | not available | not available | not available | not available | n_observations=148.6, n_train_windows=118.6, lookback=30, last_close=148.2, forecast_price=148.8, forecast_return=0.003769, train_loss=0.1056, actual_price=149, actual_return=0.005433, hit=0.65, n=20, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| wednesday | not available | not available | not available | not available | not available | n_observations=147.2, n_train_windows=117.2, lookback=30, last_close=148.4, forecast_price=148.4, forecast_return=-2.351e-05, train_loss=0.1061, actual_price=148.7, actual_return=0.001898, hit=0.5238, n=21, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| thursday | not available | not available | not available | not available | not available | n_observations=148.2, n_train_windows=118.2, lookback=30, last_close=148.7, forecast_price=147.8, forecast_return=-0.00653, train_loss=0.1053, actual_price=147.7, actual_return=-0.006278, hit=0.4762, n=21, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| friday | not available | not available | not available | not available | not available | n_observations=149.2, n_train_windows=119.2, lookback=30, last_close=147.7, forecast_price=147.7, forecast_return=1.707e-06, train_loss=0.106, actual_price=148, actual_return=0.002605, hit=0.5238, n=21, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=148, n_train_windows=118, lookback=30, last_close=148.1, forecast_price=148.4, forecast_return=0.001747, train_loss=0.109, actual_price=148.3, actual_return=0.001672, hit=0.5217, n=23, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 2 | not available | not available | not available | not available | not available | n_observations=152.8, n_train_windows=122.8, lookback=30, last_close=147.1, forecast_price=147.2, forecast_return=0.001898, train_loss=0.1054, actual_price=147, actual_return=-0.0004217, hit=0.56, n=25, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 3 | not available | not available | not available | not available | not available | n_observations=148.5, n_train_windows=118.5, lookback=30, last_close=151, forecast_price=150.3, forecast_return=-0.004568, train_loss=0.1002, actual_price=150.9, actual_return=-3.735e-05, hit=0.4211, n=19, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 4 | not available | not available | not available | not available | not available | n_observations=145.1, n_train_windows=115.1, lookback=30, last_close=149.2, forecast_price=148.8, forecast_return=-0.003697, train_loss=0.1064, actual_price=149.4, actual_return=0.001901, hit=0.5217, n=23, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 5 | not available | not available | not available | not available | not available | n_observations=151.9, n_train_windows=121.9, lookback=30, last_close=146.7, forecast_price=148.9, forecast_return=0.01493, train_loss=0.1078, actual_price=146.2, actual_return=-0.003176, hit=0.5556, n=9, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=101.5, n_train_windows=71.5, lookback=30, last_close=142.6, forecast_price=141, forecast_return=-0.01071, train_loss=0.14, actual_price=144.8, actual_return=0.01568, hit=0.75, n=4, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 6 | not available | not available | not available | not available | not available | n_observations=114, n_train_windows=84, lookback=30, last_close=137.1, forecast_price=137.9, forecast_return=0.005973, train_loss=0.1157, actual_price=136.6, actual_return=-0.002939, hit=0.4286, n=21, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=104.5, lookback=30, last_close=147, forecast_price=144.9, forecast_return=-0.01405, train_loss=0.09469, actual_price=148.1, actual_return=0.00772, hit=0.4, n=20, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=126, lookback=30, last_close=163.8, forecast_price=165.1, forecast_return=0.00766, train_loss=0.09971, actual_price=163.7, actual_return=-0.0007704, hit=0.4783, n=23, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=148, lookback=30, last_close=150.2, forecast_price=150.3, forecast_return=0.0009292, train_loss=0.1056, actual_price=149.5, actual_return=-0.004491, hit=0.619, n=21, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=163.5, lookback=30, last_close=139.3, forecast_price=140.1, forecast_return=0.005295, train_loss=0.1069, actual_price=139.3, actual_return=-0.0001045, hit=0.7, n=10, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=112, n_train_windows=82, lookback=30, last_close=138, forecast_price=138.4, forecast_return=0.003304, train_loss=0.1196, actual_price=137.9, actual_return=3.985e-05, hit=0.48, n=25, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=126.5, lookback=30, last_close=154.1, forecast_price=153.9, forecast_return=-0.001334, train_loss=0.1001, actual_price=154.2, actual_return=0.0006622, hit=0.5, n=64, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=163.5, lookback=30, last_close=139.3, forecast_price=140.1, forecast_return=0.005295, train_loss=0.1069, actual_price=139.3, actual_return=-0.0001045, hit=0.7, n=10, computed_at=2026-08-09T13:46:03.662499+00:00, run_id=4c5991037d55 |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: direction = up: n=53 (of 99)
1D: direction = down: n=45 (of 99)
1D: direction = flat: n=1 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/dlinear`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/dlinear/4c5991037d55` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._