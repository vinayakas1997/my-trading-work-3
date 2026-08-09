# lpatchtst (AAPL) -- LPatchTST LSTM+PatchTST Hybrid Forecast

**lpatchtst (AAPL):** Trained-from-scratch LPatchTST model (method 23 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/23-lpatchtst.md) — the best-performing of the six trained-from-scratch architectures in the source survey (57.7% directional accuracy per arXiv:2603.01820, corrected from an earlier miscited ~54% — see 04-enhancement-of-each-angle/13-lpatchtst.md SS1 for the correction; Sharpe 2.31-2.32). "L" is LSTM, not "lightweight": an LSTM branch and a patch-transformer branch (the same `PatchEncoderBranch` used standalone by `patchtst`) each encode the close-price lookback window, their representations are concatenated, and one linear head produces the one-step point forecast. Output: One-step-ahead forecast price/return, thresholded direction (up/down/flat), LSTM/patch branch configuration, and the fit's training-window count and final training loss.

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `lstm_hidden_size`, `n_patches`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=149, n_train_windows=117, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=148.5, forecast_price=148.1, forecast_return=-0.002756, train_loss=0.06208, actual_price=148.6, actual_return=0.0004276, hit=0.4545, close_sq_error=14.71, close_abs_error=3.073, n=99, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `lstm_hidden_size`, `n_patches`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=152.5, n_train_windows=120.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=149.9, forecast_price=149.7, forecast_return=-0.00167, train_loss=0.06174, actual_price=149.6, actual_return=-0.001817, hit=0.25, close_sq_error=16.95, close_abs_error=3.473, n=16, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| tuesday | not available | not available | not available | not available | not available | n_observations=148.6, n_train_windows=116.6, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=148.2, forecast_price=148, forecast_return=-0.001407, train_loss=0.06092, actual_price=149, actual_return=0.005433, hit=0.65, close_sq_error=4.194, close_abs_error=1.636, n=20, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| wednesday | not available | not available | not available | not available | not available | n_observations=147.2, n_train_windows=115.2, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=148.4, forecast_price=147.6, forecast_return=-0.005497, train_loss=0.06234, actual_price=148.7, actual_return=0.001898, hit=0.5238, close_sq_error=16.01, close_abs_error=3.313, n=21, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| thursday | not available | not available | not available | not available | not available | n_observations=148.2, n_train_windows=116.2, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=148.7, forecast_price=147.8, forecast_return=-0.005751, train_loss=0.06302, actual_price=147.7, actual_return=-0.006278, hit=0.4762, close_sq_error=17.64, close_abs_error=3.578, n=21, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| friday | not available | not available | not available | not available | not available | n_observations=149.2, n_train_windows=117.2, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=147.7, forecast_price=147.8, forecast_return=0.0008688, train_loss=0.06223, actual_price=148, actual_return=0.002605, hit=0.3333, close_sq_error=18.79, close_abs_error=3.391, n=21, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=148, n_train_windows=116, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=148.1, forecast_price=147.3, forecast_return=-0.005997, train_loss=0.06128, actual_price=148.3, actual_return=0.001672, hit=0.3478, close_sq_error=10.74, close_abs_error=2.893, n=23, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 2 | not available | not available | not available | not available | not available | n_observations=152.8, n_train_windows=120.8, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=147.1, forecast_price=146.6, forecast_return=-0.00295, train_loss=0.06309, actual_price=147, actual_return=-0.0004217, hit=0.56, close_sq_error=24.39, close_abs_error=3.795, n=25, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 3 | not available | not available | not available | not available | not available | n_observations=148.5, n_train_windows=116.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=151, forecast_price=149.6, forecast_return=-0.008829, train_loss=0.06299, actual_price=150.9, actual_return=-3.735e-05, hit=0.6316, close_sq_error=10.94, close_abs_error=2.541, n=19, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 4 | not available | not available | not available | not available | not available | n_observations=145.1, n_train_windows=113.1, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=149.2, forecast_price=149.4, forecast_return=0.001393, train_loss=0.06166, actual_price=149.4, actual_return=0.001901, hit=0.3913, close_sq_error=12.84, close_abs_error=3.028, n=23, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 5 | not available | not available | not available | not available | not available | n_observations=151.9, n_train_windows=119.9, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=146.7, forecast_price=147.9, forecast_return=0.008287, train_loss=0.06043, actual_price=146.2, actual_return=-0.003176, hit=0.2222, close_sq_error=10.73, close_abs_error=2.764, n=9, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=101.5, n_train_windows=69.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=142.6, forecast_price=143.9, forecast_return=0.008795, train_loss=0.06523, actual_price=144.8, actual_return=0.01568, hit=0.25, close_sq_error=17.85, close_abs_error=3.656, n=4, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 6 | not available | not available | not available | not available | not available | n_observations=114, n_train_windows=82, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=137.1, forecast_price=137.6, forecast_return=0.003879, train_loss=0.06156, actual_price=136.6, actual_return=-0.002939, hit=0.5714, close_sq_error=21.66, close_abs_error=3.612, n=21, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=102.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=147, forecast_price=146.2, forecast_return=-0.005777, train_loss=0.05485, actual_price=148.1, actual_return=0.00772, hit=0.3, close_sq_error=15.33, close_abs_error=3.437, n=20, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=124, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=163.8, forecast_price=164.3, forecast_return=0.00293, train_loss=0.06197, actual_price=163.7, actual_return=-0.0007704, hit=0.3478, close_sq_error=5.947, close_abs_error=2.187, n=23, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=146, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=150.2, forecast_price=148.3, forecast_return=-0.01212, train_loss=0.06669, actual_price=149.5, actual_return=-0.004491, hit=0.5714, close_sq_error=17.15, close_abs_error=3.246, n=21, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=161.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=139.3, forecast_price=138.1, forecast_return=-0.008686, train_loss=0.06694, actual_price=139.3, actual_return=-0.0001045, hit=0.6, close_sq_error=12.66, close_abs_error=2.651, n=10, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=112, n_train_windows=80, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=138, forecast_price=138.6, forecast_return=0.004666, train_loss=0.06214, actual_price=137.9, actual_return=3.985e-05, hit=0.52, close_sq_error=21.05, close_abs_error=3.619, n=25, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=124.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=154.1, forecast_price=153.4, forecast_return=-0.004728, train_loss=0.06129, actual_price=154.2, actual_return=0.0006622, hit=0.4062, close_sq_error=12.56, close_abs_error=2.925, n=64, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=161.5, lookback=32, lstm_hidden_size=16, n_patches=7, last_close=139.3, forecast_price=138.1, forecast_return=-0.008686, train_loss=0.06694, actual_price=139.3, actual_return=-0.0001045, hit=0.6, close_sq_error=12.66, close_abs_error=2.651, n=10, computed_at=2026-08-09T13:46:03.899551+00:00, run_id=ab2280718deb |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: direction = down: n=59 (of 99)
1D: direction = up: n=40 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/lpatchtst`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/lpatchtst/ab2280718deb` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._