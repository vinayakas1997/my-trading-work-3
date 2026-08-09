# patchtst (AAPL) -- PatchTST Channel-Independent Patch Transformer

**patchtst (AAPL):** Trained-from-scratch PatchTST model (method 20 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/20-patchtst.md) — splits the close-price lookback window into fixed-length patches, embeds each as a token, and runs a small transformer encoder's self-attention across patches (channel-independent design, a regularizer per the source survey). Fit via a handful of Adam epochs at request time; produces a one-step point forecast thresholded to a direction. See `lpatchtst` for the LSTM+PatchTST hybrid built on the same shared patch-encoder core. Output: One-step-ahead forecast price/return, thresholded direction (up/down/flat), patch configuration, and the fit's training-window count and final training loss.

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `patch_len`, `n_patches`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=149, n_train_windows=117, lookback=32, patch_len=8, n_patches=7, last_close=148.5, forecast_price=148.3, forecast_return=-0.001462, train_loss=0.06374, actual_price=148.6, actual_return=0.0004276, hit=0.4646, close_sq_error=15.66, close_abs_error=3.143, n=99, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `patch_len`, `n_patches`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=152.5, n_train_windows=120.5, lookback=32, patch_len=8, n_patches=7, last_close=149.9, forecast_price=150.3, forecast_return=0.002781, train_loss=0.06266, actual_price=149.6, actual_return=-0.001817, hit=0.375, close_sq_error=23.15, close_abs_error=4.054, n=16, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| tuesday | not available | not available | not available | not available | not available | n_observations=148.6, n_train_windows=116.6, lookback=32, patch_len=8, n_patches=7, last_close=148.2, forecast_price=148, forecast_return=-0.001558, train_loss=0.06538, actual_price=149, actual_return=0.005433, hit=0.4, close_sq_error=6.932, close_abs_error=2.315, n=20, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| wednesday | not available | not available | not available | not available | not available | n_observations=147.2, n_train_windows=115.2, lookback=32, patch_len=8, n_patches=7, last_close=148.4, forecast_price=148.1, forecast_return=-0.002136, train_loss=0.06351, actual_price=148.7, actual_return=0.001898, hit=0.6667, close_sq_error=11.3, close_abs_error=2.725, n=21, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| thursday | not available | not available | not available | not available | not available | n_observations=148.2, n_train_windows=116.2, lookback=32, patch_len=8, n_patches=7, last_close=148.7, forecast_price=147.6, forecast_return=-0.007349, train_loss=0.06382, actual_price=147.7, actual_return=-0.006278, hit=0.4762, close_sq_error=19.07, close_abs_error=3.533, n=21, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| friday | not available | not available | not available | not available | not available | n_observations=149.2, n_train_windows=117.2, lookback=32, patch_len=8, n_patches=7, last_close=147.7, forecast_price=147.9, forecast_return=0.001959, train_loss=0.06315, actual_price=148, actual_return=0.002605, hit=0.381, close_sq_error=19.19, close_abs_error=3.265, n=21, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=148, n_train_windows=116, lookback=32, patch_len=8, n_patches=7, last_close=148.1, forecast_price=148.1, forecast_return=-0.0006283, train_loss=0.064, actual_price=148.3, actual_return=0.001672, hit=0.5217, close_sq_error=8.122, close_abs_error=2.35, n=23, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 2 | not available | not available | not available | not available | not available | n_observations=152.8, n_train_windows=120.8, lookback=32, patch_len=8, n_patches=7, last_close=147.1, forecast_price=146.1, forecast_return=-0.005884, train_loss=0.06343, actual_price=147, actual_return=-0.0004217, hit=0.44, close_sq_error=30.04, close_abs_error=4.492, n=25, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 3 | not available | not available | not available | not available | not available | n_observations=148.5, n_train_windows=116.5, lookback=32, patch_len=8, n_patches=7, last_close=151, forecast_price=149.8, forecast_return=-0.007533, train_loss=0.06421, actual_price=150.9, actual_return=-3.735e-05, hit=0.4737, close_sq_error=14.01, close_abs_error=3.081, n=19, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 4 | not available | not available | not available | not available | not available | n_observations=145.1, n_train_windows=113.1, lookback=32, patch_len=8, n_patches=7, last_close=149.2, forecast_price=149.7, forecast_return=0.003329, train_loss=0.06356, actual_price=149.4, actual_return=0.001901, hit=0.4348, close_sq_error=10.88, close_abs_error=2.656, n=23, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 5 | not available | not available | not available | not available | not available | n_observations=151.9, n_train_windows=119.9, lookback=32, patch_len=8, n_patches=7, last_close=146.7, forecast_price=148.1, forecast_return=0.009267, train_loss=0.06341, actual_price=146.2, actual_return=-0.003176, hit=0.4444, close_sq_error=10.64, close_abs_error=2.796, n=9, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=101.5, n_train_windows=69.5, lookback=32, patch_len=8, n_patches=7, last_close=142.6, forecast_price=143.5, forecast_return=0.005945, train_loss=0.07485, actual_price=144.8, actual_return=0.01568, hit=0.25, close_sq_error=13.86, close_abs_error=3.256, n=4, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 6 | not available | not available | not available | not available | not available | n_observations=114, n_train_windows=82, lookback=32, patch_len=8, n_patches=7, last_close=137.1, forecast_price=138.5, forecast_return=0.01054, train_loss=0.06603, actual_price=136.6, actual_return=-0.002939, hit=0.619, close_sq_error=21.57, close_abs_error=3.387, n=21, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=102.5, lookback=32, patch_len=8, n_patches=7, last_close=147, forecast_price=146.6, forecast_return=-0.002815, train_loss=0.05276, actual_price=148.1, actual_return=0.00772, hit=0.35, close_sq_error=13.37, close_abs_error=3.323, n=20, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=124, lookback=32, patch_len=8, n_patches=7, last_close=163.8, forecast_price=164, forecast_return=0.001595, train_loss=0.06093, actual_price=163.7, actual_return=-0.0007704, hit=0.3043, close_sq_error=12.63, close_abs_error=2.888, n=23, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=146, lookback=32, patch_len=8, n_patches=7, last_close=150.2, forecast_price=148.6, forecast_return=-0.01073, train_loss=0.07024, actual_price=149.5, actual_return=-0.004491, hit=0.5714, close_sq_error=17.11, close_abs_error=3.155, n=21, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=161.5, lookback=32, patch_len=8, n_patches=7, last_close=139.3, forecast_price=137.3, forecast_return=-0.0145, train_loss=0.06927, actual_price=139.3, actual_return=-0.0001045, hit=0.6, close_sq_error=12.43, close_abs_error=2.786, n=10, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=112, n_train_windows=80, lookback=32, patch_len=8, n_patches=7, last_close=138, forecast_price=139.3, forecast_return=0.009807, train_loss=0.06744, actual_price=137.9, actual_return=3.985e-05, hit=0.56, close_sq_error=20.34, close_abs_error=3.366, n=25, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=124.5, lookback=32, patch_len=8, n_patches=7, last_close=154.1, forecast_price=153.5, forecast_return=-0.003826, train_loss=0.06143, actual_price=154.2, actual_return=0.0006622, hit=0.4062, close_sq_error=14.33, close_abs_error=3.111, n=64, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=161.5, lookback=32, patch_len=8, n_patches=7, last_close=139.3, forecast_price=137.3, forecast_return=-0.0145, train_loss=0.06927, actual_price=139.3, actual_return=-0.0001045, hit=0.6, close_sq_error=12.43, close_abs_error=2.786, n=10, computed_at=2026-08-09T13:46:03.855058+00:00, run_id=038b386f2154 |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: direction = down: n=52 (of 99)
1D: direction = up: n=47 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/patchtst`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/patchtst/038b386f2154` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._