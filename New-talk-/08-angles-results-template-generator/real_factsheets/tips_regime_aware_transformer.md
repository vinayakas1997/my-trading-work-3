# tips_regime_aware_transformer (AAPL) -- TIPS Regime-Aware Transformer Forecast

**tips_regime_aware_transformer (AAPL):** Trained-from-scratch regime-aware transformer (method 24 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/24-tips-regime-aware-transformer.md) — detects the current regime (momentum vs. mean-reversion, via trailing lag-1 return autocorrelation) and synthesizes a regime-tuned inductive prior by routing a shared transformer encoder's pooled representation through one of two regime-specific linear output heads. Produces a one-step point forecast conditioned on, and an auxiliary label for, the detected regime. Output: One-step-ahead forecast price/return, thresholded direction (up/down/flat), detected regime label (momentum/mean_reversion) and its underlying autocorrelation statistic, the regime mix seen during training, and the fit's training-window count and final training loss.

Real data covers 2022-06-24 to 2022-10-14 (112 days), 79 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `regime_window`, `last_close`, `forecast_price`, `forecast_return`, `regime_autocorr`, `n_momentum_windows`, `n_mean_reversion_windows`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=159, n_train_windows=135, lookback=24, regime_window=20, last_close=151.1, forecast_price=149.2, forecast_return=-0.01195, regime_autocorr=-0.04835, n_momentum_windows=72.57, n_mean_reversion_windows=62.43, train_loss=0.2204, actual_price=151.1, actual_return=0.0002603, hit=0.519, close_sq_error=65.61, close_abs_error=6.472, n=79, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `regime_window`, `last_close`, `forecast_price`, `forecast_return`, `regime_autocorr`, `n_momentum_windows`, `n_mean_reversion_windows`, `train_loss`, `actual_price`, `actual_return`, `hit`, `close_sq_error`, `close_abs_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=158.6, n_train_windows=134.6, lookback=24, regime_window=20, last_close=151.9, forecast_price=149.2, forecast_return=-0.01737, regime_autocorr=-0.04927, n_momentum_windows=72.36, n_mean_reversion_windows=62.29, train_loss=0.2206, actual_price=151.3, actual_return=-0.003586, hit=0.5, close_sq_error=45.45, close_abs_error=4.859, n=14, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| tuesday | not available | not available | not available | not available | not available | n_observations=158.2, n_train_windows=134.2, lookback=24, regime_window=20, last_close=150.5, forecast_price=149.8, forecast_return=-0.004475, regime_autocorr=-0.04312, n_momentum_windows=72.31, n_mean_reversion_windows=61.88, train_loss=0.2239, actual_price=151.5, actual_return=0.006147, hit=0.3125, close_sq_error=61.64, close_abs_error=6.246, n=16, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| wednesday | not available | not available | not available | not available | not available | n_observations=159.2, n_train_windows=135.2, lookback=24, regime_window=20, last_close=151.5, forecast_price=149.4, forecast_return=-0.01253, regime_autocorr=-0.06588, n_momentum_windows=72.69, n_mean_reversion_windows=62.5, train_loss=0.2173, actual_price=151.9, actual_return=0.002854, hit=0.5625, close_sq_error=73.3, close_abs_error=7.309, n=16, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| thursday | not available | not available | not available | not available | not available | n_observations=160.2, n_train_windows=136.2, lookback=24, regime_window=20, last_close=151.9, forecast_price=149, forecast_return=-0.01769, regime_autocorr=-0.04324, n_momentum_windows=73, n_mean_reversion_windows=63.19, train_loss=0.2148, actual_price=150.6, actual_return=-0.008363, hit=0.4375, close_sq_error=93.04, close_abs_error=7.893, n=16, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| friday | not available | not available | not available | not available | not available | n_observations=158.8, n_train_windows=134.8, lookback=24, regime_window=20, last_close=150, forecast_price=148.4, forecast_return=-0.008575, regime_autocorr=-0.04081, n_momentum_windows=72.47, n_mean_reversion_windows=62.29, train_loss=0.2252, actual_price=150.4, actual_return=0.003562, hit=0.7647, close_sq_error=52.91, close_abs_error=5.888, n=17, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=159.7, n_train_windows=135.7, lookback=24, regime_window=20, last_close=149, forecast_price=147.9, forecast_return=-0.006724, regime_autocorr=0.0236, n_momentum_windows=72.56, n_mean_reversion_windows=63.11, train_loss=0.203, actual_price=149.3, actual_return=0.002357, hit=0.3889, close_sq_error=74.9, close_abs_error=7.725, n=18, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 2 | not available | not available | not available | not available | not available | n_observations=163.2, n_train_windows=139.2, lookback=24, regime_window=20, last_close=149.9, forecast_price=148.7, forecast_return=-0.007353, regime_autocorr=-0.005426, n_momentum_windows=74.8, n_mean_reversion_windows=64.45, train_loss=0.208, actual_price=150.5, actual_return=0.003729, hit=0.45, close_sq_error=49.02, close_abs_error=5.528, n=20, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 3 | not available | not available | not available | not available | not available | n_observations=157.3, n_train_windows=133.3, lookback=24, regime_window=20, last_close=156.4, forecast_price=151.7, forecast_return=-0.02697, regime_autocorr=-0.1587, n_momentum_windows=72.67, n_mean_reversion_windows=60.67, train_loss=0.2484, actual_price=156.3, actual_return=-5.259e-05, hit=0.6, close_sq_error=81.89, close_abs_error=7.177, n=15, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 4 | not available | not available | not available | not available | not available | n_observations=155.4, n_train_windows=131.4, lookback=24, regime_window=20, last_close=152.2, forecast_price=149.1, forecast_return=-0.02014, regime_autocorr=-0.09953, n_momentum_windows=70.67, n_mean_reversion_windows=60.78, train_loss=0.2255, actual_price=151.6, actual_return=-0.003848, hit=0.6111, close_sq_error=59.92, close_abs_error=5.508, n=18, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 5 | not available | not available | not available | not available | not available | n_observations=158, n_train_windows=134, lookback=24, regime_window=20, last_close=146.8, forecast_price=148.4, forecast_return=0.01139, regime_autocorr=0.004542, n_momentum_windows=71.12, n_mean_reversion_windows=62.88, train_loss=0.2269, actual_price=146.3, actual_return=-0.003299, hit=0.625, close_sq_error=68.46, close_abs_error=6.861, n=8, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 6 | not available | not available | not available | not available | not available | n_observations=122, n_train_windows=98, lookback=24, regime_window=20, last_close=136.7, forecast_price=132.8, forecast_return=-0.02838, regime_autocorr=0.111, n_momentum_windows=59, n_mean_reversion_windows=39, train_loss=0.1351, actual_price=136.1, actual_return=-0.004154, hit=0.6, close_sq_error=14.79, close_abs_error=3.321, n=5, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=110.5, lookback=24, regime_window=20, last_close=147, forecast_price=141.7, forecast_return=-0.03496, regime_autocorr=-0.04706, n_momentum_windows=67, n_mean_reversion_windows=43.5, train_loss=0.1392, actual_price=148.1, actual_return=0.00772, hit=0.45, close_sq_error=75.21, close_abs_error=6.879, n=20, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=132, lookback=24, regime_window=20, last_close=163.8, forecast_price=157.6, forecast_return=-0.03693, regime_autocorr=-0.05323, n_momentum_windows=69.78, n_mean_reversion_windows=62.22, train_loss=0.2485, actual_price=163.7, actual_return=-0.0007704, hit=0.5652, close_sq_error=103.2, close_abs_error=8.573, n=23, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=154, lookback=24, regime_window=20, last_close=150.2, forecast_price=155.8, forecast_return=0.03706, regime_autocorr=-0.1199, n_momentum_windows=79.67, n_mean_reversion_windows=74.33, train_loss=0.2978, actual_price=149.5, actual_return=-0.004491, hit=0.5238, close_sq_error=53.2, close_abs_error=6.268, n=21, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=169.5, lookback=24, regime_window=20, last_close=139.3, forecast_price=138.9, forecast_return=-0.003187, regime_autocorr=0.03081, n_momentum_windows=82, n_mean_reversion_windows=87.5, train_loss=0.1985, actual_price=139.3, actual_return=-0.0001045, hit=0.5, close_sq_error=11.37, close_abs_error=2.829, n=10, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=122, n_train_windows=98, lookback=24, regime_window=20, last_close=136.7, forecast_price=132.8, forecast_return=-0.02838, regime_autocorr=0.111, n_momentum_windows=59, n_mean_reversion_windows=39, train_loss=0.1351, actual_price=136.1, actual_return=-0.004154, hit=0.6, close_sq_error=14.79, close_abs_error=3.321, n=5, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=132.5, lookback=24, regime_window=20, last_close=154.1, forecast_price=152, forecast_return=-0.01204, regime_autocorr=-0.07317, n_momentum_windows=72.16, n_mean_reversion_windows=60.34, train_loss=0.2305, actual_price=154.2, actual_return=0.0006622, hit=0.5156, close_sq_error=78.06, close_abs_error=7.287, n=64, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=169.5, lookback=24, regime_window=20, last_close=139.3, forecast_price=138.9, forecast_return=-0.003187, regime_autocorr=0.03081, n_momentum_windows=82, n_mean_reversion_windows=87.5, train_loss=0.1985, actual_price=139.3, actual_return=-0.0001045, hit=0.5, close_sq_error=11.37, close_abs_error=2.829, n=10, computed_at=2026-08-09T13:46:04.058178+00:00, run_id=54eed5e982fc |

## Status counts by time format
1D: status = ok: n=79 (of 79)
1D: direction = down: n=49 (of 79)
1D: direction = up: n=30 (of 79)
1D: regime = mean_reversion: n=50 (of 79)
1D: regime = momentum: n=29 (of 79)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/tips_regime_aware_transformer`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/tips_regime_aware_transformer/54eed5e982fc` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._