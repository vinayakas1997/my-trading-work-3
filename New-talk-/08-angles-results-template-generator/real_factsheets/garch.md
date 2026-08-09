# garch (AAPL) -- GARCH Volatility Forecast

**garch (AAPL):** Standalone GARCH(1,1) conditional-variance forecast — the classical, zero-footprint volatility baseline (method 26 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/26-garch.md). Extracted from shock_personality, which already fits GARCH internally for its own vol_persistence field (via vinu_tools.compute.risk.volatility .garch_volatility) — this angle exposes the same underlying fit as its own first-class result rather than duplicating the math. Output: Forecasted next-period volatility plus fitted GARCH(1,1) parameters

Condition: N=99 candles of history considered before each forecast ("99 candles" means 99 candles at that column's own resolution -- 99 one-minute candles for the `1min` column, 99 daily candles for the `1D` column, not a fixed time window applied to every column).

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `next_period_volatility_forecast`, `next_period_variance_forecast`, `alpha`, `beta`, `omega`, `persistence`, `actual_next_return`, `realized_variance`, `qlike_error`, `vol_direction_hit`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.0215, next_period_variance_forecast=0.0004723, alpha=0.07847, beta=0.8663, omega=2.931e-05, persistence=0.9447, actual_next_return=0.0004276, realized_variance=0.0004508, qlike_error=1.373, vol_direction_hit=0.7172, n=99, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `next_period_volatility_forecast`, `next_period_variance_forecast`, `alpha`, `beta`, `omega`, `persistence`, `actual_next_return`, `realized_variance`, `qlike_error`, `vol_direction_hit`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02132, next_period_variance_forecast=0.0004608, alpha=0.07569, beta=0.8655, omega=3.091e-05, persistence=0.9412, actual_next_return=-0.001817, realized_variance=0.0004183, qlike_error=2.022, vol_direction_hit=0.625, n=16, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| tuesday | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02162, next_period_variance_forecast=0.0004784, alpha=0.07958, beta=0.8673, omega=2.861e-05, persistence=0.9469, actual_next_return=0.005433, realized_variance=0.0002333, qlike_error=1.449, vol_direction_hit=0.65, n=20, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| wednesday | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02125, next_period_variance_forecast=0.00046, alpha=0.07979, beta=0.8662, omega=2.853e-05, persistence=0.946, actual_next_return=0.001898, realized_variance=0.0005917, qlike_error=1.122, vol_direction_hit=0.8095, n=21, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| thursday | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02152, next_period_variance_forecast=0.0004728, alpha=0.07882, beta=0.866, omega=2.918e-05, persistence=0.9449, actual_next_return=-0.006278, realized_variance=0.0005754, qlike_error=0.9055, vol_direction_hit=0.7143, n=21, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| friday | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02178, next_period_variance_forecast=0.0004869, alpha=0.07787, beta=0.8661, omega=2.967e-05, persistence=0.944, actual_next_return=0.002605, realized_variance=0.0004174, qlike_error=1.527, vol_direction_hit=0.7619, n=21, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02137, next_period_variance_forecast=0.0004648, alpha=0.0695, beta=0.8773, omega=2.777e-05, persistence=0.9468, actual_next_return=0.001672, realized_variance=0.0002934, qlike_error=1.429, vol_direction_hit=0.7826, n=23, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 2 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02119, next_period_variance_forecast=0.00046, alpha=0.0726, beta=0.8717, omega=2.916e-05, persistence=0.9443, actual_next_return=-0.0004217, realized_variance=0.0006213, qlike_error=1.573, vol_direction_hit=0.72, n=25, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 3 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02176, next_period_variance_forecast=0.0004817, alpha=0.0906, beta=0.8455, omega=3.453e-05, persistence=0.9361, actual_next_return=-3.735e-05, realized_variance=0.0003479, qlike_error=0.9226, vol_direction_hit=0.6842, n=19, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 4 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02159, next_period_variance_forecast=0.0004788, alpha=0.08724, beta=0.862, omega=2.726e-05, persistence=0.9493, actual_next_return=0.001901, realized_variance=0.0005544, qlike_error=1.546, vol_direction_hit=0.8261, n=23, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 5 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02196, next_period_variance_forecast=0.0004887, alpha=0.06972, beta=0.8776, omega=2.789e-05, persistence=0.9473, actual_next_return=-0.003176, realized_variance=0.0003325, qlike_error=1.185, vol_direction_hit=0.3333, n=9, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.0275, next_period_variance_forecast=0.0007585, alpha=0.1276, beta=0.8233, omega=2.845e-05, persistence=0.9509, actual_next_return=0.01568, realized_variance=0.0006551, qlike_error=1.808, vol_direction_hit=0.5, n=4, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 6 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02497, next_period_variance_forecast=0.0006262, alpha=0.1135, beta=0.8358, omega=3.004e-05, persistence=0.9493, actual_next_return=-0.002939, realized_variance=0.0005659, qlike_error=0.992, vol_direction_hit=0.8571, n=21, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 7 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02026, next_period_variance_forecast=0.0004141, alpha=0.11, beta=0.8185, omega=3.989e-05, persistence=0.9284, actual_next_return=0.00772, realized_variance=0.000345, qlike_error=1.021, vol_direction_hit=0.6, n=20, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 8 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02012, next_period_variance_forecast=0.0004081, alpha=0.08011, beta=0.8544, omega=3.528e-05, persistence=0.9346, actual_next_return=-0.0007704, realized_variance=0.0002518, qlike_error=2.049, vol_direction_hit=0.7391, n=23, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 9 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02006, next_period_variance_forecast=0.0004138, alpha=0.03914, beta=0.9213, omega=1.725e-05, persistence=0.9604, actual_next_return=-0.004491, realized_variance=0.0006033, qlike_error=1.362, vol_direction_hit=0.619, n=21, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 10 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02052, next_period_variance_forecast=0.0004214, alpha=0.001122, beta=0.9547, omega=1.856e-05, persistence=0.9558, actual_next_return=-0.0001045, realized_variance=0.0004767, qlike_error=1.176, vol_direction_hit=0.9, n=10, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02538, next_period_variance_forecast=0.0006474, alpha=0.1158, beta=0.8338, omega=2.979e-05, persistence=0.9496, actual_next_return=3.985e-05, realized_variance=0.0005802, qlike_error=1.123, vol_direction_hit=0.8, n=25, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 3 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02014, next_period_variance_forecast=0.0004118, alpha=0.076, beta=0.8651, omega=3.081e-05, persistence=0.9411, actual_next_return=0.0006622, realized_variance=0.0003963, qlike_error=1.502, vol_direction_hit=0.6562, n=64, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |
| 4 | not available | not available | not available | not available | not available | n_observations=99, next_period_volatility_forecast=0.02052, next_period_variance_forecast=0.0004214, alpha=0.001122, beta=0.9547, omega=1.856e-05, persistence=0.9558, actual_next_return=-0.0001045, realized_variance=0.0004767, qlike_error=1.176, vol_direction_hit=0.9, n=10, computed_at=2026-08-09T13:29:48.244397+00:00, run_id=b91076318517 |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: forecasted_vol_direction = rising: n=67 (of 99)
1D: forecasted_vol_direction = falling: n=32 (of 99)
1D: actual_vol_direction = rising: n=53 (of 99)
1D: actual_vol_direction = falling: n=46 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/garch`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/garch/b91076318517` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._