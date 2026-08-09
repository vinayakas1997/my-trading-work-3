# lstm (AAPL) -- LSTM Sequential Forecast

**lstm (AAPL):** Trained-from-scratch single-layer LSTM (method 19 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/19-lstm.md) — the classical recurrent baseline among the six trained-from-scratch architectures the source survey found competitive on finance. Processes a rolling close-price window step-by-step through gated memory cells, fit via a handful of Adam epochs at request time, producing a one-step point forecast thresholded to a direction. Output: One-step-ahead forecast price/return, thresholded direction (up/down/flat), and the fit's training-window count and final training loss.

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `hidden_size`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=149, n_train_windows=119, lookback=30, hidden_size=16, last_close=148.5, forecast_price=148.7, forecast_return=0.001475, train_loss=0.0848, actual_price=148.6, actual_return=0.0004276, hit=0.4545, close_sq_error=12.3, close_abs_error=2.854, n=99, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `hidden_size`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=152.5, n_train_windows=122.5, lookback=30, hidden_size=16, last_close=149.9, forecast_price=150.5, forecast_return=0.003776, train_loss=0.08305, actual_price=149.6, actual_return=-0.001817, hit=0.25, close_sq_error=14.38, close_abs_error=3.272, n=16, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| tuesday | not available | not available | not available | not available | not available | n_observations=148.6, n_train_windows=118.6, lookback=30, hidden_size=16, last_close=148.2, forecast_price=148.4, forecast_return=0.001722, train_loss=0.08451, actual_price=149, actual_return=0.005433, hit=0.6, close_sq_error=4.269, close_abs_error=1.72, n=20, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| wednesday | not available | not available | not available | not available | not available | n_observations=147.2, n_train_windows=117.2, lookback=30, hidden_size=16, last_close=148.4, forecast_price=148.2, forecast_return=-0.001001, train_loss=0.08563, actual_price=148.7, actual_return=0.001898, hit=0.381, close_sq_error=15.48, close_abs_error=3.227, n=21, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| thursday | not available | not available | not available | not available | not available | n_observations=148.2, n_train_windows=118.2, lookback=30, hidden_size=16, last_close=148.7, forecast_price=148.6, forecast_return=-0.0001746, train_loss=0.08527, actual_price=147.7, actual_return=-0.006278, hit=0.4762, close_sq_error=15.41, close_abs_error=3.296, n=21, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| friday | not available | not available | not available | not available | not available | n_observations=149.2, n_train_windows=119.2, lookback=30, hidden_size=16, last_close=147.7, forecast_price=148.2, forecast_return=0.003611, train_loss=0.08508, actual_price=148, actual_return=0.002605, hit=0.5238, close_sq_error=12.07, close_abs_error=2.801, n=21, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=148, n_train_windows=118, lookback=30, hidden_size=16, last_close=148.1, forecast_price=147.9, forecast_return=-0.0015, train_loss=0.08776, actual_price=148.3, actual_return=0.001672, hit=0.4348, close_sq_error=8.142, close_abs_error=2.302, n=23, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 2 | not available | not available | not available | not available | not available | n_observations=152.8, n_train_windows=122.8, lookback=30, hidden_size=16, last_close=147.1, forecast_price=147.6, forecast_return=0.004154, train_loss=0.08452, actual_price=147, actual_return=-0.0004217, hit=0.52, close_sq_error=16.64, close_abs_error=3.368, n=25, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 3 | not available | not available | not available | not available | not available | n_observations=148.5, n_train_windows=118.5, lookback=30, hidden_size=16, last_close=151, forecast_price=151.2, forecast_return=0.001842, train_loss=0.08123, actual_price=150.9, actual_return=-3.735e-05, hit=0.3684, close_sq_error=9.358, close_abs_error=2.666, n=19, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 4 | not available | not available | not available | not available | not available | n_observations=145.1, n_train_windows=115.1, lookback=30, hidden_size=16, last_close=149.2, forecast_price=149.2, forecast_return=0.0001619, train_loss=0.08523, actual_price=149.4, actual_return=0.001901, hit=0.4783, close_sq_error=15.17, close_abs_error=3.089, n=23, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 5 | not available | not available | not available | not available | not available | n_observations=151.9, n_train_windows=121.9, lookback=30, hidden_size=16, last_close=146.7, forecast_price=147.3, forecast_return=0.004212, train_loss=0.08443, actual_price=146.2, actual_return=-0.003176, hit=0.4444, close_sq_error=9.736, close_abs_error=2.633, n=9, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=101.5, n_train_windows=71.5, lookback=30, hidden_size=16, last_close=142.6, forecast_price=140.7, forecast_return=-0.01294, train_loss=0.1238, actual_price=144.8, actual_return=0.01568, hit=0.5, close_sq_error=23.49, close_abs_error=4.04, n=4, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 6 | not available | not available | not available | not available | not available | n_observations=114, n_train_windows=84, lookback=30, hidden_size=16, last_close=137.1, forecast_price=138.2, forecast_return=0.008514, train_loss=0.09949, actual_price=136.6, actual_return=-0.002939, hit=0.619, close_sq_error=14.8, close_abs_error=2.997, n=21, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=104.5, lookback=30, hidden_size=16, last_close=147, forecast_price=146.7, forecast_return=-0.001753, train_loss=0.07475, actual_price=148.1, actual_return=0.00772, hit=0.35, close_sq_error=10.24, close_abs_error=2.645, n=20, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=126, lookback=30, hidden_size=16, last_close=163.8, forecast_price=164, forecast_return=0.0009168, train_loss=0.07744, actual_price=163.7, actual_return=-0.0007704, hit=0.3478, close_sq_error=8.298, close_abs_error=2.448, n=23, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=148, lookback=30, hidden_size=16, last_close=150.2, forecast_price=150.4, forecast_return=0.00149, train_loss=0.08108, actual_price=149.5, actual_return=-0.004491, hit=0.4762, close_sq_error=15.25, close_abs_error=3.17, n=21, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=163.5, lookback=30, hidden_size=16, last_close=139.3, forecast_price=139.3, forecast_return=0.0001626, train_loss=0.08313, actual_price=139.3, actual_return=-0.0001045, hit=0.5, close_sq_error=9.681, close_abs_error=2.767, n=10, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=112, n_train_windows=82, lookback=30, hidden_size=16, last_close=138, forecast_price=138.6, forecast_return=0.005082, train_loss=0.1034, actual_price=137.9, actual_return=3.985e-05, hit=0.6, close_sq_error=16.19, close_abs_error=3.164, n=25, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=126.5, lookback=30, hidden_size=16, last_close=154.1, forecast_price=154.1, forecast_return=0.0002704, train_loss=0.07779, actual_price=154.2, actual_return=0.0006622, hit=0.3906, close_sq_error=11.19, close_abs_error=2.746, n=64, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=163.5, lookback=30, hidden_size=16, last_close=139.3, forecast_price=139.3, forecast_return=0.0001626, train_loss=0.08313, actual_price=139.3, actual_return=-0.0001045, hit=0.5, close_sq_error=9.681, close_abs_error=2.767, n=10, computed_at=2026-08-09T13:46:03.804593+00:00, run_id=0a57c1e9946b |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: direction = down: n=51 (of 99)
1D: direction = up: n=48 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/lstm`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/lstm/0a57c1e9946b` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._