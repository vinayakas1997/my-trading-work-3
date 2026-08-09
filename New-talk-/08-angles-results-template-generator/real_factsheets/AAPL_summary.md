# Angle results summary -- AAPL

One section per angle, in a fixed order. No comparison or ranking across sections is implied by that order.

---

# chronos (AAPL) -- Chronos Time-Series Foundation Model

**chronos (AAPL):** Zero-shot probabilistic forecast from Amazon's Chronos-T5 time-series foundation model (method 10 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/10-chronos.md). General-purpose, not finance-specific — a comparison baseline against Kronos, not a first-choice signal (per the spec's own caveat that general TSFMs tend to underperform finance-specific models on K-line data). Output: Quantile forecast (p10/median/p90) for the next 5 periods, plus model_backend ("pretrained" via amazon/chronos-t5-large, or "fallback_proxy" if the real pipeline could not be loaded).

Real data covers 2024-01-17 to 2024-03-19 (62 days), 44 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | last_close=180.7, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=181, n=8, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| tuesday | not available | not available | not available | not available | not available | last_close=180.5, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| wednesday | not available | not available | not available | not available | not available | last_close=180.1, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| thursday | not available | not available | not available | not available | not available | last_close=181.1, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| friday | not available | not available | not available | not available | not available | last_close=181, n=9, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=178.1, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 2 | not available | not available | not available | not available | not available | last_close=177.5, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 3 | not available | not available | not available | not available | not available | last_close=179.7, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 4 | not available | not available | not available | not available | not available | last_close=186.2, n=10, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 5 | not available | not available | not available | not available | not available | last_close=184.5, n=4, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=188.6, n=11, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 2 | not available | not available | not available | not available | not available | last_close=182.7, n=20, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 3 | not available | not available | not available | not available | not available | last_close=171.1, n=13, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=180.7, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`p10`, `median`, `p90`, `actual`, `hit`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | p10=177.9, median=180.8, p90=183.7, actual=180.6, hit=0.8864, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 2 | not available | not available | not available | not available | not available | p10=176.6, median=181, p90=185, actual=180.3, hit=0.7955, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 3 | not available | not available | not available | not available | not available | p10=175.6, median=181.2, p90=186.1, actual=179.8, hit=0.7273, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 4 | not available | not available | not available | not available | not available | p10=174.7, median=181.4, p90=187, actual=179.3, hit=0.75, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |
| 5 | not available | not available | not available | not available | not available | p10=173.9, median=181.4, p90=188, actual=178.8, hit=0.6818, n=44, computed_at=2026-08-09T13:43:35.551256+00:00, run_id=3951acb61e1c |

## Status counts by time format
1D: status = ok: n=44 (of 44)
1D: model_backend = pretrained: n=44 (of 44)
1D: checkpoint = amazon/chronos-t5-large: n=44 (of 44)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/chronos`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/chronos/3951acb61e1c` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

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

---

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

---

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

---

# kronos (AAPL) -- Kronos Financial K-Line Foundation Model

**kronos (AAPL):** Next-K-line forecast using the real Kronos pretrained model (method 9 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/09-kronos.md) — the flagship open-source financial K-line foundation model (AAAI 2026), a tokenizer + autoregressive decoder-only transformer pretrained on 12B K-line records from 45 exchanges. Weights + tokenizer are downloaded into the shared models dir (`make models`); the custom model code is vendored (MIT) into `_kronos_model/`. Falls back to an honestly-labeled in-process-trained MLP proxy only if the weights or load are unavailable at runtime. See compute.py's module docstring for the full explanation. Output: Predicted next-bar OHLC plus a 5-step OHLC forecast, model_backend ("pretrained" or "fallback_proxy") and fallback_reason explaining why.

Real data covers 2024-01-17 to 2024-03-19 (62 days), 44 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | last_close=180.7, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=181, n=8, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| tuesday | not available | not available | not available | not available | not available | last_close=180.5, n=9, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| wednesday | not available | not available | not available | not available | not available | last_close=180.1, n=9, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| thursday | not available | not available | not available | not available | not available | last_close=181.1, n=9, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| friday | not available | not available | not available | not available | not available | last_close=181, n=9, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=178.1, n=10, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 2 | not available | not available | not available | not available | not available | last_close=177.5, n=10, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 3 | not available | not available | not available | not available | not available | last_close=179.7, n=10, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 4 | not available | not available | not available | not available | not available | last_close=186.2, n=10, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 5 | not available | not available | not available | not available | not available | last_close=184.5, n=4, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=188.6, n=11, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 2 | not available | not available | not available | not available | not available | last_close=182.7, n=20, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 3 | not available | not available | not available | not available | not available | last_close=171.1, n=13, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=180.7, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`open`, `high`, `low`, `close`, `actual_close`, `hit`, `close_sq_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | open=180.8, high=182.7, low=179.2, close=180.9, actual_close=180.6, hit=0.5227, close_sq_error=5.244, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 2 | not available | not available | not available | not available | not available | open=180.7, high=182.3, low=178.8, close=180.4, actual_close=180.3, hit=0.5227, close_sq_error=12.08, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 3 | not available | not available | not available | not available | not available | open=180.2, high=181.9, low=178.5, close=180.1, actual_close=179.8, hit=0.6136, close_sq_error=22.67, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 4 | not available | not available | not available | not available | not available | open=179.8, high=181.5, low=178.1, close=179.7, actual_close=179.3, hit=0.5909, close_sq_error=34.44, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |
| 5 | not available | not available | not available | not available | not available | open=179.4, high=181.3, low=177.7, close=179.5, actual_close=178.8, hit=0.4091, close_sq_error=41.37, n=44, computed_at=2026-08-09T13:43:35.671452+00:00, run_id=a2e45c4065dd |

## Status counts by time format
1D: status = ok: n=44 (of 44)
1D: model_backend = pretrained: n=44 (of 44)
1D: checkpoint = NeoQuasar/Kronos-base: n=44 (of 44)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/kronos`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/kronos/a2e45c4065dd` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# lag_llama (AAPL) -- Lag-Llama Probabilistic Time-Series Model (fallback proxy)

**lag_llama (AAPL):** Probabilistic (multi-quantile) forecast in the spirit of Lag-Llama (method 16 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/16-lag-llama.md). lag-llama has no PyPI package and only a manual-clone research repo — this angle uses an honestly-labeled AR(5) linear-Gaussian fallback proxy that still emits a genuinely probabilistic output. See compute.py's module docstring. Output: Point forecast plus a 5-quantile (p5/p25/p50/p75/p95) distributional forecast for the next 5 periods, plus model_backend (always "fallback_proxy") and fallback_reason.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `lag_order`, `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | lag_order=5, last_close=149, n=95, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`lag_order`, `last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | lag_order=5, last_close=149.9, n=16, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| tuesday | not available | not available | not available | not available | not available | lag_order=5, last_close=148.8, n=19, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| wednesday | not available | not available | not available | not available | not available | lag_order=5, last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| thursday | not available | not available | not available | not available | not available | lag_order=5, last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| friday | not available | not available | not available | not available | not available | lag_order=5, last_close=148.3, n=20, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | lag_order=5, last_close=148.1, n=23, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 2 | not available | not available | not available | not available | not available | lag_order=5, last_close=149, n=21, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 3 | not available | not available | not available | not available | not available | lag_order=5, last_close=151, n=19, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 4 | not available | not available | not available | not available | not available | lag_order=5, last_close=149.2, n=23, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 5 | not available | not available | not available | not available | not available | lag_order=5, last_close=146.7, n=9, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | lag_order=5, last_close=142.6, n=4, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 6 | not available | not available | not available | not available | not available | lag_order=5, last_close=137.1, n=21, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 7 | not available | not available | not available | not available | not available | lag_order=5, last_close=147, n=20, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 8 | not available | not available | not available | not available | not available | lag_order=5, last_close=163.8, n=23, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 9 | not available | not available | not available | not available | not available | lag_order=5, last_close=150.2, n=21, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 10 | not available | not available | not available | not available | not available | lag_order=5, last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | lag_order=5, last_close=138, n=25, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 3 | not available | not available | not available | not available | not available | lag_order=5, last_close=154.1, n=64, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 4 | not available | not available | not available | not available | not available | lag_order=5, last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`p5`, `p25`, `p50`, `p75`, `p95`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | p5=143.8, p25=146.9, p50=149, p75=151.2, p95=154.2, actual_close=149, hit=0.9158, close_sq_error=9.906, close_abs_error=2.501, n=95, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 2 | not available | not available | not available | not available | not available | p5=141.6, p25=146, p50=149, p75=152.1, p95=156.4, actual_close=148.9, hit=0.8947, close_sq_error=20.14, close_abs_error=3.582, n=95, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 3 | not available | not available | not available | not available | not available | p5=140, p25=145.3, p50=149, p75=152.7, p95=158.1, actual_close=148.9, hit=0.9158, close_sq_error=26.98, close_abs_error=4.215, n=95, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 4 | not available | not available | not available | not available | not available | p5=138.6, p25=144.7, p50=149, p75=153.3, p95=159.5, actual_close=148.8, hit=0.9263, close_sq_error=34.06, close_abs_error=4.783, n=95, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |
| 5 | not available | not available | not available | not available | not available | p5=137.3, p25=144.2, p50=149, p75=153.8, p95=160.7, actual_close=148.7, hit=0.9368, close_sq_error=40.28, close_abs_error=5.284, n=95, computed_at=2026-08-09T13:46:40.672635+00:00, run_id=5c7da8a9ea14 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = fallback_proxy: n=95 (of 95)
1D: fallback_reason = lag-llama has no PyPI package (confirmed via pip install attempt); the only public artifact is a research GitHub repo requiring a manual clone plus a separately-hosted checkpoint, not achievable in the a-few-minutes-per-model budget. Using an in-process lagged-value (AR) linear-Gaussian fallback proxy that still emits a genuinely probabilistic (multi-quantile) forecast, matching the spec's differentiator, in place of the real LLaMA-architecture model.: n=95 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)
1D: quantile_levels = [0.05 0.25 0.5  0.75 0.95]: n=1 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/lag_llama`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/lag_llama/5c7da8a9ea14` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# moirai (AAPL) -- MOIRAI Any-Variate Time-Series Foundation Model (fallback proxy)

**moirai (AAPL):** Forecast in the spirit of Salesforce's MOIRAI (method 13 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/13-moirai.md). The real `uni2ts` package exists but would downgrade the shared environment's torch build and can't exercise MOIRAI's any-variate multi-ticker mechanism from this per-symbol interface anyway — this angle uses an honestly-labeled AR(3) statistical fallback proxy. See compute.py's module docstring. Output: Point + p10/p90 forecast for the next 5 periods, plus model_backend (always "fallback_proxy"), fallback_reason, and any_variate_note explaining the single-ticker degeneration.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | last_close=149, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=149.9, n=16, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| tuesday | not available | not available | not available | not available | not available | last_close=148.8, n=19, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| wednesday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| thursday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| friday | not available | not available | not available | not available | not available | last_close=148.3, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=148.1, n=23, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 2 | not available | not available | not available | not available | not available | last_close=149, n=21, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 3 | not available | not available | not available | not available | not available | last_close=151, n=19, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 4 | not available | not available | not available | not available | not available | last_close=149.2, n=23, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 5 | not available | not available | not available | not available | not available | last_close=146.7, n=9, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | last_close=142.6, n=4, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 6 | not available | not available | not available | not available | not available | last_close=137.1, n=21, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 7 | not available | not available | not available | not available | not available | last_close=147, n=20, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 8 | not available | not available | not available | not available | not available | last_close=163.8, n=23, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 9 | not available | not available | not available | not available | not available | last_close=150.2, n=21, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 10 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | last_close=138, n=25, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 3 | not available | not available | not available | not available | not available | last_close=154.1, n=64, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 4 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`point`, `p10`, `p90`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | point=149, p10=144.9, p90=153.1, actual_close=149, hit=0.8105, close_sq_error=9.612, close_abs_error=2.419, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 2 | not available | not available | not available | not available | not available | point=149, p10=143.2, p90=154.8, actual_close=148.9, hit=0.8316, close_sq_error=20.1, close_abs_error=3.592, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 3 | not available | not available | not available | not available | not available | point=149, p10=141.9, p90=156.1, actual_close=148.9, hit=0.8316, close_sq_error=27.36, close_abs_error=4.266, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 4 | not available | not available | not available | not available | not available | point=149, p10=140.8, p90=157.2, actual_close=148.8, hit=0.7895, close_sq_error=34.83, close_abs_error=4.851, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |
| 5 | not available | not available | not available | not available | not available | point=149, p10=139.9, p90=158.1, actual_close=148.7, hit=0.8632, close_sq_error=40.9, close_abs_error=5.327, n=95, computed_at=2026-08-09T13:46:40.794740+00:00, run_id=b58d6015fed8 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = fallback_proxy: n=95 (of 95)
1D: fallback_reason = uni2ts (real MOIRAI package) would downgrade the shared environment's torch 2.13.0+cpu to torch==2.4.1 plus pull in jax/lightning — too risky to install for one angle; additionally this angle's per-symbol compute() call can't exercise MOIRAI's any-variate multi-ticker mechanism anyway, so a single-series AR(3) statistical proxy is used instead, explicitly labeled as the any-variate-degenerate case.: n=95 (of 95)
1D: any_variate_note = This call is single-ticker only (compute() receives one symbol's bars at a time) — MOIRAI's any-variate joint-multi-series mechanism is not exercised; this is the single-variate degenerate case.: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/moirai`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/moirai/b58d6015fed8` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# moment (AAPL) -- MOMENT Multi-Task Time-Series Foundation Model (fallback proxy)

**moment (AAPL):** Forecast in the spirit of MOMENT's forecasting task (method 14 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/14-moment.md). The real `momentfm` package failed to build in this Python 3.12 environment (pkgutil.ImpImporter incompatibility, confirmed via an actual install attempt) — this angle uses an honestly-labeled statistical fallback proxy for the forecasting task only. See compute.py's module docstring. Output: Point + p10/p90 forecast for the next 5 periods, plus model_backend (always "fallback_proxy"), fallback_reason, and task_note flagging that only the forecasting task is implemented.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | last_close=149, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | last_close=149.9, n=16, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| tuesday | not available | not available | not available | not available | not available | last_close=148.8, n=19, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| wednesday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| thursday | not available | not available | not available | not available | not available | last_close=149.1, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| friday | not available | not available | not available | not available | not available | last_close=148.3, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | last_close=148.1, n=23, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 2 | not available | not available | not available | not available | not available | last_close=149, n=21, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 3 | not available | not available | not available | not available | not available | last_close=151, n=19, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 4 | not available | not available | not available | not available | not available | last_close=149.2, n=23, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 5 | not available | not available | not available | not available | not available | last_close=146.7, n=9, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | last_close=142.6, n=4, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 6 | not available | not available | not available | not available | not available | last_close=137.1, n=21, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 7 | not available | not available | not available | not available | not available | last_close=147, n=20, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 8 | not available | not available | not available | not available | not available | last_close=163.8, n=23, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 9 | not available | not available | not available | not available | not available | last_close=150.2, n=21, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 10 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | last_close=138, n=25, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 3 | not available | not available | not available | not available | not available | last_close=154.1, n=64, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 4 | not available | not available | not available | not available | not available | last_close=140.8, n=6, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`point`, `p10`, `p90`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | point=149.1, p10=145, p90=153.2, actual_close=149, hit=0.8, close_sq_error=9.797, close_abs_error=2.533, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 2 | not available | not available | not available | not available | not available | point=149.1, p10=143.3, p90=154.9, actual_close=148.9, hit=0.8316, close_sq_error=21.11, close_abs_error=3.597, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 3 | not available | not available | not available | not available | not available | point=149.2, p10=142.1, p90=156.3, actual_close=148.9, hit=0.7789, close_sq_error=29.68, close_abs_error=4.189, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 4 | not available | not available | not available | not available | not available | point=149.2, p10=141, p90=157.4, actual_close=148.8, hit=0.8105, close_sq_error=37.96, close_abs_error=4.91, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |
| 5 | not available | not available | not available | not available | not available | point=149.3, p10=140.1, p90=158.5, actual_close=148.7, hit=0.8, close_sq_error=44.12, close_abs_error=5.281, n=95, computed_at=2026-08-09T13:46:40.848198+00:00, run_id=099bed1d7c60 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = fallback_proxy: n=95 (of 95)
1D: fallback_reason = momentfm (real MOMENT package) failed to build in this environment: "AttributeError: module 'pkgutil' has no attribute 'ImpImporter'" — a genuine Python 3.12 incompatibility in one of its transitive build dependencies, confirmed via `pip install momentfm`. Using a statistical fallback proxy for the forecasting task only; MOMENT's embeddings/anomaly-detection/imputation tasks are not implemented.: n=95 (of 95)
1D: task_note = forecasting task only — embeddings/anomaly_detection/imputation not implemented: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/moment`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/moment/099bed1d7c60` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# timesfm (AAPL) -- TimesFM Time-Series Foundation Model

**timesfm (AAPL):** Zero-shot point + quantile forecast from Google's TimesFM foundation model (method 11 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/11-timesfm.md). General-purpose, not finance-specific — a comparison baseline alongside Chronos and Kronos, not a first-choice signal. Output: Point forecast plus all 9 real decile levels (q10 through q90 — the model's own trained quantile-head output, genuine model confidence, not a bolted-on statistical band) for the next 5 periods, plus context_length_used, model_backend ("pretrained" via google/timesfm-2.5-200m-pytorch, or "fallback_proxy" if the real checkpoint could not be loaded) and fallback_reason.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `context_length_used`, `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | context_length_used=147, last_close=149, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`context_length_used`, `last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | context_length_used=152.5, last_close=149.9, n=16, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| tuesday | not available | not available | not available | not available | not available | context_length_used=146.2, last_close=148.8, n=19, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| wednesday | not available | not available | not available | not available | not available | context_length_used=144.8, last_close=149.1, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| thursday | not available | not available | not available | not available | not available | context_length_used=145.8, last_close=149.1, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| friday | not available | not available | not available | not available | not available | context_length_used=146.8, last_close=148.3, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | context_length_used=148, last_close=148.1, n=23, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 2 | not available | not available | not available | not available | not available | context_length_used=144.5, last_close=149, n=21, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 3 | not available | not available | not available | not available | not available | context_length_used=148.5, last_close=151, n=19, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 4 | not available | not available | not available | not available | not available | context_length_used=145.1, last_close=149.2, n=23, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 5 | not available | not available | not available | not available | not available | context_length_used=151.9, last_close=146.7, n=9, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | context_length_used=101.5, last_close=142.6, n=4, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 6 | not available | not available | not available | not available | not available | context_length_used=114, last_close=137.1, n=21, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 7 | not available | not available | not available | not available | not available | context_length_used=134.5, last_close=147, n=20, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 8 | not available | not available | not available | not available | not available | context_length_used=156, last_close=163.8, n=23, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 9 | not available | not available | not available | not available | not available | context_length_used=178, last_close=150.2, n=21, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 10 | not available | not available | not available | not available | not available | context_length_used=191.5, last_close=140.8, n=6, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | context_length_used=112, last_close=138, n=25, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 3 | not available | not available | not available | not available | not available | context_length_used=156.5, last_close=154.1, n=64, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 4 | not available | not available | not available | not available | not available | context_length_used=191.5, last_close=140.8, n=6, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`q10`, `q20`, `q30`, `q40`, `q50`, `q60`, `q70`, `q80`, `q90`, `actual_close`, `hit`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | q10=143.1, q20=145.5, q30=147.1, q40=148.1, q50=149.1, q60=150.1, q70=151.2, q80=152.7, q90=154.9, actual_close=149, hit=0.9158, close_sq_error=10.1, close_abs_error=2.485, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 2 | not available | not available | not available | not available | not available | q10=141.7, q20=144.7, q30=146.4, q40=148, q50=149.2, q60=150.6, q70=152.2, q80=153.8, q90=156.5, actual_close=148.9, hit=0.8842, close_sq_error=20.76, close_abs_error=3.637, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 3 | not available | not available | not available | not available | not available | q10=140.3, q20=143.8, q30=146.1, q40=147.8, q50=149.3, q60=150.9, q70=152.6, q80=154.9, q90=158, actual_close=148.9, hit=0.8842, close_sq_error=29.04, close_abs_error=4.371, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 4 | not available | not available | not available | not available | not available | q10=139.2, q20=143.3, q30=145.9, q40=147.5, q50=149.5, q60=151.5, q70=153.1, q80=155.6, q90=159.5, actual_close=148.8, hit=0.8947, close_sq_error=38.48, close_abs_error=5.11, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |
| 5 | not available | not available | not available | not available | not available | q10=138.3, q20=142.8, q30=145.5, q40=147.5, q50=149.6, q60=151.7, q70=153.9, q80=156.5, q90=160.6, actual_close=148.7, hit=0.9053, close_sq_error=45, close_abs_error=5.582, n=95, computed_at=2026-08-09T13:30:24.507910+00:00, run_id=ba89ad03e587 |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = pretrained: n=95 (of 95)
1D: checkpoint = google/timesfm-2.5-200m-pytorch: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/timesfm`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/timesfm/ba89ad03e587` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# timer_timerxl (AAPL) -- Timer / Timer-XL Patch-Based Foundation Model

**timer_timerxl (AAPL):** Patch-based forecast using the real Timer pretrained model (method 15 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/15-timer-timerxl.md) — THUML's `thuml/timer-base-84m` (84M params), a decoder-only causal transformer pretrained on 260B time points, patch length 96. Weights are downloaded into the shared models dir (`make models`). Falls back to an honestly-labeled patch-based statistical proxy (per-patch mean log-return trend extrapolation) only if the weights or load are unavailable at runtime. See compute.py's module docstring for the full explanation. (Corrected 2026-08 — this file previously read "(fallback proxy)" and claimed no installable package existed, both stale since the 2026-08-06 models-wiring pass; found and fixed during angle 27's implementation, matching the same correction already applied to kronos's spec.yaml.) Output: Point forecast for the next 5 periods (the real model's native output) plus a post-hoc p10/p90 residual-normal band (not native model uncertainty), checkpoint/patch_size/n_patches, model_backend ("pretrained" in the normal case, "fallback_proxy" only if real inference fails at runtime) and fallback_reason.

Real data covers 2022-05-25 to 2022-10-10 (138 days), 95 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `patch_size`, `n_patches`, `last_close`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=149, n=95, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`patch_size`, `n_patches`, `last_close`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=149.9, n=16, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| tuesday | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=148.8, n=19, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| wednesday | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=149.1, n=20, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| thursday | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=149.1, n=20, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| friday | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=148.3, n=20, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=148.1, n=23, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 2 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=149, n=21, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 3 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=151, n=19, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 4 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=149.2, n=23, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 5 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=146.7, n=9, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=142.6, n=4, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 6 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=137.1, n=21, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 7 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=147, n=20, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 8 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=163.8, n=23, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 9 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=150.2, n=21, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 10 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=140.8, n=6, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=138, n=25, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 3 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=154.1, n=64, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 4 | not available | not available | not available | not available | not available | patch_size=96, n_patches=1, last_close=140.8, n=6, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |

## Breakdown by forecast horizon step

This angle stores a real nested `predictions` field: one entry per horizon step ahead of the forecast origin (`horizon=1` is the nearest real step forecast, higher numbers further out). Fields below (`point`, `p10`, `p90`, `actual`, `hit`, `in_band`, `close_sq_error`, `close_abs_error`) are each real horizon step's own mean across every real step at that horizon, plus `n` (how many real steps that mean is based on). A field that only ever holds 0/1 in the raw data (e.g. `hit`) has a mean that is a real hit rate: the fraction of real steps where it was 1.

| horizon | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | point=149, p10=144.6, p90=153.4, actual=149, hit=0.5474, in_band=0.8526, close_sq_error=9.334, close_abs_error=2.431, n=95, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 2 | not available | not available | not available | not available | not available | point=149.9, p10=143.6, p90=156.1, actual=148.9, hit=0.5263, in_band=0.8105, close_sq_error=19.97, close_abs_error=3.575, n=95, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 3 | not available | not available | not available | not available | not available | point=150.5, p10=142.8, p90=158.1, actual=148.9, hit=0.5789, in_band=0.8842, close_sq_error=27.33, close_abs_error=4.146, n=95, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 4 | not available | not available | not available | not available | not available | point=150.9, p10=142.1, p90=159.7, actual=148.8, hit=0.6211, in_band=0.8842, close_sq_error=35.04, close_abs_error=4.523, n=95, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |
| 5 | not available | not available | not available | not available | not available | point=151.3, p10=141.4, p90=161.1, actual=148.7, hit=0.6632, in_band=0.8947, close_sq_error=41.46, close_abs_error=4.78, n=95, computed_at=2026-08-09T13:30:08.587814+00:00, run_id=dfdc114ce78a |

## Status counts by time format
1D: status = ok: n=95 (of 95)
1D: model_backend = pretrained: n=95 (of 95)
1D: checkpoint = thuml/timer-base-84m: n=95 (of 95)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/timer_timerxl`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/timer_timerxl/dfdc114ce78a` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# backtesting_44_metrics (AAPL) -- Backtesting Metrics

**backtesting_44_metrics (AAPL):** Compute 44+ portfolio metrics — Sharpe, Sortino, MaxDD, WinRate, CAGR, VaR, CVaR, tail ratio Output: Angle-specific results

Condition: N=100 candles of history considered before each forecast ("100 candles" means 100 candles at that column's own resolution -- 100 one-minute candles for the `1min` column, 100 daily candles for the `1D` column, not a fixed time window applied to every column).

Real data covers 2022-05-26 to 2022-10-17 (144 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D, 1W, 1M, 6M). Each cell states `n_observations`, `total_return`, `cagr`, `ann_vol`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `win_rate`, `avg_win`, `avg_loss`, `win_loss_ratio`, `profit_factor`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M | 6M |
|---|---|---|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.07554, cagr=-0.1684, ann_vol=0.3611, sharpe_ratio=-0.4669, sortino_ratio=-0.7177, max_drawdown=-0.2455, calmar_ratio=-0.6858, win_rate=0.5049, avg_win=0.01747, avg_loss=-0.01901, win_loss_ratio=0.9278, profit_factor=0.9449, n=99, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| london | not available | not available | not available | not available | not available | not available (n=0) | not available | not available | not available |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) | not available | not available | not available |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) | not available | not available | not available |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) | not available | not available | not available |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `total_return`, `cagr`, `ann_vol`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `win_rate`, `avg_win`, `avg_loss`, `win_loss_ratio`, `profit_factor`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M | 6M |
|---|---|---|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.06185, cagr=-0.1379, ann_vol=0.3615, sharpe_ratio=-0.3826, sortino_ratio=-0.5869, max_drawdown=-0.2454, calmar_ratio=-0.5575, win_rate=0.5047, avg_win=0.01762, avg_loss=-0.01884, win_loss_ratio=0.9439, profit_factor=0.9601, n=17, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| tuesday | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.08374, cagr=-0.1882, ann_vol=0.3616, sharpe_ratio=-0.5197, sortino_ratio=-0.7981, max_drawdown=-0.2459, calmar_ratio=-0.7621, win_rate=0.504, avg_win=0.01746, avg_loss=-0.01908, win_loss_ratio=0.9228, profit_factor=0.9361, n=20, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| wednesday | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.07504, cagr=-0.1673, ann_vol=0.3607, sharpe_ratio=-0.4622, sortino_ratio=-0.709, max_drawdown=-0.2448, calmar_ratio=-0.6758, win_rate=0.506, avg_win=0.01741, avg_loss=-0.01902, win_loss_ratio=0.9248, profit_factor=0.9458, n=20, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| thursday | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.07596, cagr=-0.1677, ann_vol=0.3605, sharpe_ratio=-0.4668, sortino_ratio=-0.7203, max_drawdown=-0.2453, calmar_ratio=-0.6862, win_rate=0.5052, avg_win=0.01742, avg_loss=-0.01901, win_loss_ratio=0.9257, profit_factor=0.9442, n=21, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| friday | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.07887, cagr=-0.1759, ann_vol=0.3613, sharpe_ratio=-0.4892, sortino_ratio=-0.7529, max_drawdown=-0.2459, calmar_ratio=-0.726, win_rate=0.5048, avg_win=0.01747, avg_loss=-0.01907, win_loss_ratio=0.9245, profit_factor=0.9408, n=21, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M | 6M |
|---|---|---|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.06888, cagr=-0.1508, ann_vol=0.3595, sharpe_ratio=-0.4233, sortino_ratio=-0.6619, max_drawdown=-0.2417, calmar_ratio=-0.6318, win_rate=0.5057, avg_win=0.01747, avg_loss=-0.01894, win_loss_ratio=0.9305, profit_factor=0.9514, n=23, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 2 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.06694, cagr=-0.1466, ann_vol=0.3583, sharpe_ratio=-0.4058, sortino_ratio=-0.6309, max_drawdown=-0.2423, calmar_ratio=-0.6019, win_rate=0.502, avg_win=0.01747, avg_loss=-0.01862, win_loss_ratio=0.9484, profit_factor=0.9548, n=25, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 3 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.05938, cagr=-0.135, ann_vol=0.3653, sharpe_ratio=-0.367, sortino_ratio=-0.5607, max_drawdown=-0.2528, calmar_ratio=-0.5221, win_rate=0.514, avg_win=0.01756, avg_loss=-0.01937, win_loss_ratio=0.9155, profit_factor=0.9646, n=20, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 4 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.09513, cagr=-0.2146, ann_vol=0.3618, sharpe_ratio=-0.5964, sortino_ratio=-0.9069, max_drawdown=-0.2489, calmar_ratio=-0.8627, win_rate=0.5027, avg_win=0.01741, avg_loss=-0.01919, win_loss_ratio=0.914, profit_factor=0.9225, n=22, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 5 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.1044, cagr=-0.2349, ann_vol=0.3617, sharpe_ratio=-0.653, sortino_ratio=-0.9887, max_drawdown=-0.2393, calmar_ratio=-0.9878, win_rate=0.4967, avg_win=0.01746, avg_loss=-0.019, win_loss_ratio=0.9247, profit_factor=0.9117, n=9, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M | 6M |
|---|---|---|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.1734, cagr=-0.3798, ann_vol=0.3441, sharpe_ratio=-1.105, sortino_ratio=-1.771, max_drawdown=-0.232, calmar_ratio=-1.637, win_rate=0.4867, avg_win=0.0163, avg_loss=-0.01871, win_loss_ratio=0.8713, profit_factor=0.8265, n=3, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 6 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.1727, cagr=-0.3787, ann_vol=0.3589, sharpe_ratio=-1.054, sortino_ratio=-1.641, max_drawdown=-0.2543, calmar_ratio=-1.489, win_rate=0.4948, avg_win=0.01689, avg_loss=-0.01979, win_loss_ratio=0.8545, profit_factor=0.8366, n=21, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 7 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.1023, cagr=-0.2317, ann_vol=0.3687, sharpe_ratio=-0.6304, sortino_ratio=-0.9802, max_drawdown=-0.2703, calmar_ratio=-0.8575, win_rate=0.5325, avg_win=0.01716, avg_loss=-0.02132, win_loss_ratio=0.8049, profit_factor=0.9188, n=20, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 8 | not available | not available | not available | not available | not available | n_observations=100, total_return=0.0008218, cagr=0.007489, ann_vol=0.3656, sharpe_ratio=0.01919, sortino_ratio=0.0295, max_drawdown=-0.2652, calmar_ratio=0.01384, win_rate=0.5187, avg_win=0.01789, avg_loss=-0.01876, win_loss_ratio=0.9549, profit_factor=1.03, n=23, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 9 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.05565, cagr=-0.1331, ann_vol=0.3634, sharpe_ratio=-0.3671, sortino_ratio=-0.5264, max_drawdown=-0.2121, calmar_ratio=-0.6366, win_rate=0.49, avg_win=0.01792, avg_loss=-0.01784, win_loss_ratio=1.005, profit_factor=0.9659, n=21, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 10 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.01245, cagr=-0.02895, ann_vol=0.3421, sharpe_ratio=-0.08186, sortino_ratio=-0.1194, max_drawdown=-0.2097, calmar_ratio=-0.138, win_rate=0.4791, avg_win=0.01774, avg_loss=-0.01612, win_loss_ratio=1.102, profit_factor=1.013, n=11, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D | 1W | 1M | 6M |
|---|---|---|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.1728, cagr=-0.3789, ann_vol=0.3571, sharpe_ratio=-1.06, sortino_ratio=-1.657, max_drawdown=-0.2515, calmar_ratio=-1.507, win_rate=0.4937, avg_win=0.01682, avg_loss=-0.01966, win_loss_ratio=0.8566, profit_factor=0.8353, n=24, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 3 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.04993, cagr=-0.1134, ann_vol=0.3659, sharpe_ratio=-0.3105, sortino_ratio=-0.4684, max_drawdown=-0.2493, calmar_ratio=-0.4719, win_rate=0.5136, avg_win=0.01767, avg_loss=-0.01926, win_loss_ratio=0.9246, profit_factor=0.9742, n=64, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |
| 4 | not available | not available | not available | not available | not available | n_observations=100, total_return=-0.01245, cagr=-0.02895, ann_vol=0.3421, sharpe_ratio=-0.08186, sortino_ratio=-0.1194, max_drawdown=-0.2097, calmar_ratio=-0.138, win_rate=0.4791, avg_win=0.01774, avg_loss=-0.01612, win_loss_ratio=1.102, profit_factor=1.013, n=11, computed_at=2026-08-09T13:29:48.370425+00:00, run_id=7031e7071766 | not available | not available | not available |

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/backtesting_44_metrics`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/backtesting_44_metrics/7031e7071766` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# arima (AAPL) -- ARIMA Classical Statistical Baseline

**arima (AAPL):** AutoRegressive Integrated Moving Average forecast — the classical statistical baseline (method 25 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/25-arima.md). Fits an ARIMA(p, d, q) model to the close-price series with order chosen by AIC grid search, no fixed lookback window, and reports the model's standard output shape: a one-step-ahead point forecast plus its 95% confidence interval. Output: Fitted ARIMA order, AIC, one-step-ahead point forecast, and 95% confidence interval

Condition: N=100 candles of history considered before each forecast ("100 candles" means 100 candles at that column's own resolution -- 100 one-minute candles for the `1min` column, 100 daily candles for the `1D` column, not a fixed time window applied to every column).

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations` (number of historical bars the model was fit on for this step), `aic` (Akaike information criterion of the fitted model at this step), `forecast` (the model's point forecast for the next close), `confidence_level` (the confidence level the interval was built at), `actual_price` (the real next close the forecast is checked against), `hit_rate` (fraction of steps where the real next close landed inside that step's own 95% confidence interval -- not a direction guess), `abs_error` (absolute difference between forecast and actual_price), `squared_error` (squared difference between forecast and actual_price), plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=100, aic=527.6, forecast=148.6, confidence_level=0.95, actual_price=148.6, hit_rate=0.9596, abs_error=2.617, squared_error=10.51, n=99, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `aic`, `forecast`, `confidence_level`, `actual_price`, `hit_rate`, `abs_error`, `squared_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=100, aic=527.6, forecast=150, confidence_level=0.95, actual_price=149.6, hit_rate=0.9375, abs_error=2.45, squared_error=10.03, n=16, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| tuesday | not available | not available | not available | not available | not available | n_observations=100, aic=527.9, forecast=148, confidence_level=0.95, actual_price=149, hit_rate=1, abs_error=1.702, squared_error=4.85, n=20, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| wednesday | not available | not available | not available | not available | not available | n_observations=100, aic=527.3, forecast=148.5, confidence_level=0.95, actual_price=148.7, hit_rate=0.9048, abs_error=3.157, squared_error=14.06, n=21, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| thursday | not available | not available | not available | not available | not available | n_observations=100, aic=527.8, forecast=148.8, confidence_level=0.95, actual_price=147.7, hit_rate=1, abs_error=3.124, squared_error=13.03, n=21, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| friday | not available | not available | not available | not available | not available | n_observations=100, aic=527.5, forecast=147.8, confidence_level=0.95, actual_price=148, hit_rate=0.9524, abs_error=2.565, squared_error=10.19, n=21, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=100, aic=526.3, forecast=148, confidence_level=0.95, actual_price=148.3, hit_rate=1, abs_error=1.825, squared_error=5.428, n=23, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 2 | not available | not available | not available | not available | not available | n_observations=100, aic=525.3, forecast=147.2, confidence_level=0.95, actual_price=147, hit_rate=0.92, abs_error=3.163, squared_error=14.48, n=25, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 3 | not available | not available | not available | not available | not available | n_observations=100, aic=530.4, forecast=151, confidence_level=0.95, actual_price=150.9, hit_rate=1, abs_error=2.664, squared_error=9.106, n=19, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 4 | not available | not available | not available | not available | not available | n_observations=100, aic=528.7, forecast=149.2, confidence_level=0.95, actual_price=149.4, hit_rate=0.913, abs_error=2.9, squared_error=13.56, n=23, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 5 | not available | not available | not available | not available | not available | n_observations=100, aic=528.8, forecast=147.2, confidence_level=0.95, actual_price=146.2, hit_rate=1, abs_error=2.296, squared_error=7.623, n=9, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=100, aic=527.3, forecast=142.6, confidence_level=0.95, actual_price=144.8, hit_rate=1, abs_error=2.74, squared_error=12.9, n=4, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 6 | not available | not available | not available | not available | not available | n_observations=100, aic=532.2, forecast=137.1, confidence_level=0.95, actual_price=136.6, hit_rate=0.9524, abs_error=2.903, squared_error=12.16, n=21, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 7 | not available | not available | not available | not available | not available | n_observations=100, aic=533.1, forecast=146.9, confidence_level=0.95, actual_price=148.1, hit_rate=0.95, abs_error=2.216, squared_error=7.816, n=20, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 8 | not available | not available | not available | not available | not available | n_observations=100, aic=527.9, forecast=163.9, confidence_level=0.95, actual_price=163.7, hit_rate=1, abs_error=2.505, squared_error=8.725, n=23, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 9 | not available | not available | not available | not available | not available | n_observations=100, aic=526.5, forecast=150.5, confidence_level=0.95, actual_price=149.5, hit_rate=0.9048, abs_error=3.115, squared_error=14.81, n=21, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 10 | not available | not available | not available | not available | not available | n_observations=100, aic=509.1, forecast=139.2, confidence_level=0.95, actual_price=139.3, hit_rate=1, abs_error=1.979, squared_error=6.536, n=10, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=100, aic=531.4, forecast=138, confidence_level=0.95, actual_price=137.9, hit_rate=0.96, abs_error=2.877, squared_error=12.28, n=25, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 3 | not available | not available | not available | not available | not available | n_observations=100, aic=529, forecast=154.2, confidence_level=0.95, actual_price=154.2, hit_rate=0.9531, abs_error=2.615, squared_error=10.44, n=64, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |
| 4 | not available | not available | not available | not available | not available | n_observations=100, aic=509.1, forecast=139.2, confidence_level=0.95, actual_price=139.3, hit_rate=1, abs_error=1.979, squared_error=6.536, n=10, computed_at=2026-08-09T13:29:48.050284+00:00, run_id=d5a63714dc45 |

## Status counts by time format
1D: status = ok: n=99 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/arima`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/arima/d5a63714dc45` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

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

---

# drawdown_deep_dive (AAPL) -- Drawdown Deep-Dive

**drawdown_deep_dive (AAPL):** Drawdown detection, news attribution, max drawdown duration, recovery time across multi-timeframe Output: Angle-specific results

Real data covers 2022-02-09 to 2022-03-30 (49 days), 2 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `episode_index`, `k`, `peak_ts`, `peak_price`, `atr_pct_at_peak`, `threshold_pct_used`, `trough_ts`, `trough_price`, `drop_pct`, `duration_to_trough`, `trough_speed`, `recovery_ts`, `recovery_price`, `recovery_gain_pct`, `duration_to_recovery`, `recovery_speed`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | episode_index=0.5, k=2, peak_ts=1.646e+09, peak_price=174.4, atr_pct_at_peak=2.494, threshold_pct_used=-4.987, trough_ts=1.651e+09, trough_price=137.6, drop_pct=-21.01, duration_to_trough=38, trough_speed=-0.5875, recovery_ts=1.649e+09, recovery_price=175.1, recovery_gain_pct=18.77, duration_to_recovery=11, recovery_speed=1.707, n=2, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`episode_index`, `k`, `peak_ts`, `peak_price`, `atr_pct_at_peak`, `threshold_pct_used`, `trough_ts`, `trough_price`, `drop_pct`, `duration_to_trough`, `trough_speed`, `recovery_ts`, `recovery_price`, `recovery_gain_pct`, `duration_to_recovery`, `recovery_speed`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| wednesday | not available | not available | not available | not available | not available | episode_index=0.5, k=2, peak_ts=1.646e+09, peak_price=174.4, atr_pct_at_peak=2.494, threshold_pct_used=-4.987, trough_ts=1.651e+09, trough_price=137.6, drop_pct=-21.01, duration_to_trough=38, trough_speed=-0.5875, recovery_ts=1.649e+09, recovery_price=175.1, recovery_gain_pct=18.77, duration_to_recovery=11, recovery_speed=1.707, n=2, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | episode_index=0, k=2, peak_ts=1.644e+09, peak_price=172.9, atr_pct_at_peak=2.661, threshold_pct_used=-5.322, trough_ts=1.647e+09, trough_price=147.4, drop_pct=-14.72, duration_to_trough=22, trough_speed=-0.6693, recovery_ts=1.649e+09, recovery_price=175.1, recovery_gain_pct=18.77, duration_to_recovery=11, recovery_speed=1.707, n=1, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |
| 5 | not available | not available | not available | not available | not available | episode_index=1, k=2, peak_ts=1.649e+09, peak_price=175.8, atr_pct_at_peak=2.326, threshold_pct_used=-4.652, trough_ts=1.655e+09, trough_price=127.8, drop_pct=-27.3, duration_to_trough=54, trough_speed=-0.5056, recovery_ts=nan, recovery_price=nan, recovery_gain_pct=nan, duration_to_recovery=nan, recovery_speed=nan, n=1, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | episode_index=0, k=2, peak_ts=1.644e+09, peak_price=172.9, atr_pct_at_peak=2.661, threshold_pct_used=-5.322, trough_ts=1.647e+09, trough_price=147.4, drop_pct=-14.72, duration_to_trough=22, trough_speed=-0.6693, recovery_ts=1.649e+09, recovery_price=175.1, recovery_gain_pct=18.77, duration_to_recovery=11, recovery_speed=1.707, n=1, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |
| 3 | not available | not available | not available | not available | not available | episode_index=1, k=2, peak_ts=1.649e+09, peak_price=175.8, atr_pct_at_peak=2.326, threshold_pct_used=-4.652, trough_ts=1.655e+09, trough_price=127.8, drop_pct=-27.3, duration_to_trough=54, trough_speed=-0.5056, recovery_ts=nan, recovery_price=nan, recovery_gain_pct=nan, duration_to_recovery=nan, recovery_speed=nan, n=1, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | episode_index=0.5, k=2, peak_ts=1.646e+09, peak_price=174.4, atr_pct_at_peak=2.494, threshold_pct_used=-4.987, trough_ts=1.651e+09, trough_price=137.6, drop_pct=-21.01, duration_to_trough=38, trough_speed=-0.5875, recovery_ts=1.649e+09, recovery_price=175.1, recovery_gain_pct=18.77, duration_to_recovery=11, recovery_speed=1.707, n=2, computed_at=2026-08-09T13:29:48.420794+00:00, run_id=70e999f8b0df |

## Status counts by time format
1D: status = recovered: n=1 (of 2)
1D: status = open: n=1 (of 2)
1D: formation_news = []: n=1 (of 2)
1D: formation_news = []: n=1 (of 2)
1D: recovery_news = []: n=1 (of 2)
1D: recovery_news = []: n=1 (of 2)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/drawdown_deep_dive`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/drawdown_deep_dive/70e999f8b0df` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# itransformer (AAPL) -- iTransformer Cross-Variate Attention Forecast

**itransformer (AAPL):** Trained-from-scratch iTransformer model (method 21 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/21-itransformer.md) — tokenizes variates (here: this symbol's OHLCV channels, since the per-symbol compute() interface has no sibling-ticker input to exploit true cross-asset attention; see compute.py's docstring for the full deviation note) rather than time steps, so self-attention runs across variate-tokens. Fit via a handful of Adam epochs at request time; reports the close-channel one-step forecast, thresholded to a direction. Output: One-step-ahead forecast for every OHLCV channel used as a variate (forecast_open/high/low/close/volume), close-channel return thresholded to a direction (up/down/flat), which channels were used, and the fit's training-window count and final training loss.

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `n_channels`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `forecast_open`, `forecast_high`, `forecast_low`, `forecast_close`, `forecast_volume`, `actual_price`, `actual_return`, `hit`, `abs_error`, `squared_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=149, n_train_windows=117, lookback=32, n_channels=5, last_close=148.5, forecast_price=148.4, forecast_return=-0.0005335, train_loss=0.1351, forecast_open=148.2, forecast_high=150.4, forecast_low=146.2, forecast_close=148.4, forecast_volume=1.565e+06, actual_price=148.6, actual_return=0.0004276, hit=0.4545, abs_error=3.667, squared_error=20.23, n=99, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `n_channels`, `last_close`, `forecast_price`, `forecast_return`, `train_loss`, `forecast_open`, `forecast_high`, `forecast_low`, `forecast_close`, `forecast_volume`, `actual_price`, `actual_return`, `hit`, `abs_error`, `squared_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=152.5, n_train_windows=120.5, lookback=32, n_channels=5, last_close=149.9, forecast_price=150, forecast_return=0.0006272, train_loss=0.1376, forecast_open=149.7, forecast_high=152, forecast_low=147.9, forecast_close=150, forecast_volume=1.501e+06, actual_price=149.6, actual_return=-0.001817, hit=0.375, abs_error=3.841, squared_error=18.3, n=16, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| tuesday | not available | not available | not available | not available | not available | n_observations=148.6, n_train_windows=116.6, lookback=32, n_channels=5, last_close=148.2, forecast_price=148.7, forecast_return=0.003866, train_loss=0.135, forecast_open=148.4, forecast_high=150.6, forecast_low=146.5, forecast_close=148.7, forecast_volume=1.487e+06, actual_price=149, actual_return=0.005433, hit=0.6, abs_error=2.955, squared_error=11.87, n=20, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| wednesday | not available | not available | not available | not available | not available | n_observations=147.2, n_train_windows=115.2, lookback=32, n_channels=5, last_close=148.4, forecast_price=148.6, forecast_return=0.0007588, train_loss=0.1318, forecast_open=148.1, forecast_high=150.4, forecast_low=146.1, forecast_close=148.6, forecast_volume=1.573e+06, actual_price=148.7, actual_return=0.001898, hit=0.4286, abs_error=3.62, squared_error=23.19, n=21, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| thursday | not available | not available | not available | not available | not available | n_observations=148.2, n_train_windows=116.2, lookback=32, n_channels=5, last_close=148.7, forecast_price=148, forecast_return=-0.004828, train_loss=0.1336, forecast_open=147.9, forecast_high=150, forecast_low=145.8, forecast_close=148, forecast_volume=1.623e+06, actual_price=147.7, actual_return=-0.006278, hit=0.4286, abs_error=4.279, squared_error=26.42, n=21, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| friday | not available | not available | not available | not available | not available | n_observations=149.2, n_train_windows=117.2, lookback=32, n_channels=5, last_close=147.7, forecast_price=147.3, forecast_return=-0.002605, train_loss=0.1379, forecast_open=147.4, forecast_high=149.4, forecast_low=145.2, forecast_close=147.3, forecast_volume=1.62e+06, actual_price=148, actual_return=0.002605, hit=0.4286, abs_error=3.646, squared_error=20.54, n=21, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=148, n_train_windows=116, lookback=32, n_channels=5, last_close=148.1, forecast_price=147.5, forecast_return=-0.004919, train_loss=0.133, forecast_open=147.3, forecast_high=149.5, forecast_low=145.2, forecast_close=147.5, forecast_volume=1.543e+06, actual_price=148.3, actual_return=0.001672, hit=0.3043, abs_error=3.15, squared_error=15.08, n=23, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 2 | not available | not available | not available | not available | not available | n_observations=152.8, n_train_windows=120.8, lookback=32, n_channels=5, last_close=147.1, forecast_price=147.9, forecast_return=0.006376, train_loss=0.1356, forecast_open=147.4, forecast_high=149.8, forecast_low=145.5, forecast_close=147.9, forecast_volume=1.406e+06, actual_price=147, actual_return=-0.0004217, hit=0.48, abs_error=4.46, squared_error=30.89, n=25, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 3 | not available | not available | not available | not available | not available | n_observations=148.5, n_train_windows=116.5, lookback=32, n_channels=5, last_close=151, forecast_price=150.7, forecast_return=-0.001577, train_loss=0.139, forecast_open=150.5, forecast_high=152.6, forecast_low=148.5, forecast_close=150.7, forecast_volume=1.611e+06, actual_price=150.9, actual_return=-3.735e-05, hit=0.5263, abs_error=2.422, squared_error=8.902, n=19, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 4 | not available | not available | not available | not available | not available | n_observations=145.1, n_train_windows=113.1, lookback=32, n_channels=5, last_close=149.2, forecast_price=148.3, forecast_return=-0.006417, train_loss=0.1324, forecast_open=148.2, forecast_high=150.2, forecast_low=146.2, forecast_close=148.3, forecast_volume=1.66e+06, actual_price=149.4, actual_return=0.001901, hit=0.4783, abs_error=4.295, squared_error=23.94, n=23, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 5 | not available | not available | not available | not available | not available | n_observations=151.9, n_train_windows=119.9, lookback=32, n_channels=5, last_close=146.7, forecast_price=148, forecast_return=0.008722, train_loss=0.1377, forecast_open=148.6, forecast_high=150.3, forecast_low=146.1, forecast_close=148, forecast_volume=1.721e+06, actual_price=146.2, actual_return=-0.003176, hit=0.5556, abs_error=3.806, squared_error=18.27, n=9, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=101.5, n_train_windows=69.5, lookback=32, n_channels=5, last_close=142.6, forecast_price=141, forecast_return=-0.01143, train_loss=0.08552, forecast_open=139.6, forecast_high=141.9, forecast_low=137.7, forecast_close=141, forecast_volume=1.892e+06, actual_price=144.8, actual_return=0.01568, hit=0.25, abs_error=4.555, squared_error=32.31, n=4, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 6 | not available | not available | not available | not available | not available | n_observations=114, n_train_windows=82, lookback=32, n_channels=5, last_close=137.1, forecast_price=139.1, forecast_return=0.01511, train_loss=0.1063, forecast_open=138.6, forecast_high=141.3, forecast_low=136.5, forecast_close=139.1, forecast_volume=1.717e+06, actual_price=136.6, actual_return=-0.002939, hit=0.5714, abs_error=4.329, squared_error=31.12, n=21, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=102.5, lookback=32, n_channels=5, last_close=147, forecast_price=144.6, forecast_return=-0.01633, train_loss=0.1376, forecast_open=144.2, forecast_high=146.5, forecast_low=142.1, forecast_close=144.6, forecast_volume=1.224e+06, actual_price=148.1, actual_return=0.00772, hit=0.4, abs_error=4.129, squared_error=21.56, n=20, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=124, lookback=32, n_channels=5, last_close=163.8, forecast_price=165.5, forecast_return=0.01045, train_loss=0.145, forecast_open=165.5, forecast_high=167.3, forecast_low=163.7, forecast_close=165.5, forecast_volume=1.252e+06, actual_price=163.7, actual_return=-0.0007704, hit=0.4348, abs_error=2.852, squared_error=12.74, n=23, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=146, lookback=32, n_channels=5, last_close=150.2, forecast_price=149.1, forecast_return=-0.007279, train_loss=0.153, forecast_open=149.3, forecast_high=151.2, forecast_low=147.3, forecast_close=149.1, forecast_volume=1.992e+06, actual_price=149.5, actual_return=-0.004491, hit=0.4286, abs_error=3.741, squared_error=18.55, n=21, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=161.5, lookback=32, n_channels=5, last_close=139.3, forecast_price=138.1, forecast_return=-0.008527, train_loss=0.1499, forecast_open=138.2, forecast_high=140.3, forecast_low=135.9, forecast_close=138.1, forecast_volume=1.618e+06, actual_price=139.3, actual_return=-0.0001045, hit=0.5, abs_error=2.715, squared_error=10.66, n=10, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=112, n_train_windows=80, lookback=32, n_channels=5, last_close=138, forecast_price=139.4, forecast_return=0.01086, train_loss=0.103, forecast_open=138.7, forecast_high=141.4, forecast_low=136.7, forecast_close=139.4, forecast_volume=1.745e+06, actual_price=137.9, actual_return=3.985e-05, hit=0.52, abs_error=4.365, squared_error=31.31, n=25, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=124.5, lookback=32, n_channels=5, last_close=154.1, forecast_price=153.6, forecast_return=-0.003737, train_loss=0.1453, forecast_open=153.5, forecast_high=155.5, forecast_low=151.5, forecast_close=153.6, forecast_volume=1.486e+06, actual_price=154.2, actual_return=0.0006622, hit=0.4219, abs_error=3.543, squared_error=17.4, n=64, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=161.5, lookback=32, n_channels=5, last_close=139.3, forecast_price=138.1, forecast_return=-0.008527, train_loss=0.1499, forecast_open=138.2, forecast_high=140.3, forecast_low=135.9, forecast_close=138.1, forecast_volume=1.618e+06, actual_price=139.3, actual_return=-0.0001045, hit=0.5, abs_error=2.715, squared_error=10.66, n=10, computed_at=2026-08-09T13:46:04.008183+00:00, run_id=03d52f88b901 |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: channels = open,high,low,close,volume: n=99 (of 99)
1D: direction = up: n=50 (of 99)
1D: direction = down: n=48 (of 99)
1D: direction = flat: n=1 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/itransformer`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/itransformer/03d52f88b901` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

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

---

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

---

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

---

# tft (AAPL) -- TFT Temporal Fusion Transformer (Quantile Forecast)

**tft (AAPL):** Trained-from-scratch, lightweight Temporal Fusion Transformer (method 22 of the 32-method plan, see New-talk-/Final-implementation/01-present-considerations/22-tft.md) — a gated variable-selection network weights engineered return/volatility features at each time step, an LSTM encodes the sequence, self-attention pools it, and three linear heads produce P10/P50/P90 next-step return quantiles trained jointly via pinball loss, per the spec's "natively quantile forecasts" output format. Known-future inputs and static covariates from the source spec are not modeled (no such data available from `bars`/`news`); see compute.py's docstring for the full note. Output: P10/P50/P90 next-step return and price quantile forecasts, thresholded direction from the median, the last-step variable-selection weights per feature, and the fit's training-window count and final training loss.

Real data covers 2022-05-25 to 2022-10-14 (142 days), 99 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `n_observations`, `n_train_windows`, `lookback`, `last_close`, `forecast_return_p10`, `forecast_return_p50`, `forecast_return_p90`, `forecast_price_p10`, `forecast_price_p50`, `forecast_price_p90`, `train_loss`, `actual_price`, `actual_return`, `hit`, `in_band`, `close_sq_error`, `close_abs_error`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | n_observations=149, n_train_windows=98, lookback=30, last_close=148.5, forecast_return_p10=-0.03066, forecast_return_p50=0.0006542, forecast_return_p90=0.02593, forecast_price_p10=144, forecast_price_p50=148.6, forecast_price_p90=152.4, train_loss=0.005991, actual_price=148.6, actual_return=0.0004276, hit=0.4747, in_band=0.7576, close_sq_error=11.3, close_abs_error=2.68, n=99, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`n_observations`, `n_train_windows`, `lookback`, `last_close`, `forecast_return_p10`, `forecast_return_p50`, `forecast_return_p90`, `forecast_price_p10`, `forecast_price_p50`, `forecast_price_p90`, `train_loss`, `actual_price`, `actual_return`, `hit`, `in_band`, `close_sq_error`, `close_abs_error`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | n_observations=152.5, n_train_windows=101.5, lookback=30, last_close=149.9, forecast_return_p10=-0.03192, forecast_return_p50=-0.0009605, forecast_return_p90=0.02479, forecast_price_p10=145.2, forecast_price_p50=149.8, forecast_price_p90=153.7, train_loss=0.0059, actual_price=149.6, actual_return=-0.001817, hit=0.4375, in_band=0.8125, close_sq_error=12.38, close_abs_error=2.539, n=16, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| tuesday | not available | not available | not available | not available | not available | n_observations=148.6, n_train_windows=97.6, lookback=30, last_close=148.2, forecast_return_p10=-0.03011, forecast_return_p50=0.001, forecast_return_p90=0.02611, forecast_price_p10=143.7, forecast_price_p50=148.4, forecast_price_p90=152.1, train_loss=0.005958, actual_price=149, actual_return=0.005433, hit=0.55, in_band=0.9, close_sq_error=4.595, close_abs_error=1.671, n=20, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| wednesday | not available | not available | not available | not available | not available | n_observations=147.2, n_train_windows=96.24, lookback=30, last_close=148.4, forecast_return_p10=-0.03017, forecast_return_p50=0.001031, forecast_return_p90=0.0259, forecast_price_p10=144, forecast_price_p50=148.6, forecast_price_p90=152.3, train_loss=0.006061, actual_price=148.7, actual_return=0.001898, hit=0.4762, in_band=0.6667, close_sq_error=12.84, close_abs_error=3.052, n=21, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| thursday | not available | not available | not available | not available | not available | n_observations=148.2, n_train_windows=97.24, lookback=30, last_close=148.7, forecast_return_p10=-0.02822, forecast_return_p50=0.002757, forecast_return_p90=0.02844, forecast_price_p10=144.5, forecast_price_p50=149.1, forecast_price_p90=152.9, train_loss=0.005923, actual_price=147.7, actual_return=-0.006278, hit=0.5238, in_band=0.7143, close_sq_error=15.38, close_abs_error=3.277, n=21, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| friday | not available | not available | not available | not available | not available | n_observations=149.2, n_train_windows=98.24, lookback=30, last_close=147.7, forecast_return_p10=-0.03316, forecast_return_p50=-0.0009249, forecast_return_p90=0.02412, forecast_price_p10=142.9, forecast_price_p50=147.6, forecast_price_p90=151.3, train_loss=0.006088, actual_price=148, actual_return=0.002605, hit=0.381, in_band=0.7143, close_sq_error=11.22, close_abs_error=2.778, n=21, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | n_observations=148, n_train_windows=97, lookback=30, last_close=148.1, forecast_return_p10=-0.03073, forecast_return_p50=0.002176, forecast_return_p90=0.0279, forecast_price_p10=143.6, forecast_price_p50=148.5, forecast_price_p90=152.3, train_loss=0.005972, actual_price=148.3, actual_return=0.001672, hit=0.4783, in_band=0.7826, close_sq_error=10.24, close_abs_error=2.228, n=23, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 2 | not available | not available | not available | not available | not available | n_observations=152.8, n_train_windows=101.8, lookback=30, last_close=147.1, forecast_return_p10=-0.0305, forecast_return_p50=0.001029, forecast_return_p90=0.02648, forecast_price_p10=142.6, forecast_price_p50=147.3, forecast_price_p90=151, train_loss=0.005908, actual_price=147, actual_return=-0.0004217, hit=0.52, in_band=0.68, close_sq_error=14.74, close_abs_error=3.127, n=25, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 3 | not available | not available | not available | not available | not available | n_observations=148.5, n_train_windows=97.53, lookback=30, last_close=151, forecast_return_p10=-0.02928, forecast_return_p50=0.001432, forecast_return_p90=0.02648, forecast_price_p10=146.6, forecast_price_p50=151.2, forecast_price_p90=155, train_loss=0.005976, actual_price=150.9, actual_return=-3.735e-05, hit=0.4737, in_band=0.7368, close_sq_error=9.386, close_abs_error=2.593, n=19, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 4 | not available | not available | not available | not available | not available | n_observations=145.1, n_train_windows=94.13, lookback=30, last_close=149.2, forecast_return_p10=-0.03068, forecast_return_p50=-0.0004616, forecast_return_p90=0.024, forecast_price_p10=144.6, forecast_price_p50=149.1, forecast_price_p90=152.7, train_loss=0.006075, actual_price=149.4, actual_return=0.001901, hit=0.5217, in_band=0.7826, close_sq_error=10.72, close_abs_error=2.651, n=23, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 5 | not available | not available | not available | not available | not available | n_observations=151.9, n_train_windows=100.9, lookback=30, last_close=146.7, forecast_return_p10=-0.03382, forecast_return_p50=-0.003066, forecast_return_p90=0.02309, forecast_price_p10=141.8, forecast_price_p50=146.3, forecast_price_p90=150.1, train_loss=0.006083, actual_price=146.2, actual_return=-0.003176, hit=0.2222, in_band=0.8889, close_sq_error=9.906, close_abs_error=2.848, n=9, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 5 | not available | not available | not available | not available | not available | n_observations=101.5, n_train_windows=50.5, lookback=30, last_close=142.6, forecast_return_p10=-0.02495, forecast_return_p50=0.005084, forecast_return_p90=0.02805, forecast_price_p10=139.1, forecast_price_p50=143.4, forecast_price_p90=146.6, train_loss=0.006666, actual_price=144.8, actual_return=0.01568, hit=0.25, in_band=0.5, close_sq_error=11.59, close_abs_error=3.078, n=4, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 6 | not available | not available | not available | not available | not available | n_observations=114, n_train_windows=63, lookback=30, last_close=137.1, forecast_return_p10=-0.03068, forecast_return_p50=0.0003411, forecast_return_p90=0.02514, forecast_price_p10=132.9, forecast_price_p50=137.2, forecast_price_p90=140.5, train_loss=0.006354, actual_price=136.6, actual_return=-0.002939, hit=0.4762, in_band=0.6667, close_sq_error=14.38, close_abs_error=3.157, n=21, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 7 | not available | not available | not available | not available | not available | n_observations=134.5, n_train_windows=83.5, lookback=30, last_close=147, forecast_return_p10=-0.03013, forecast_return_p50=0.003375, forecast_return_p90=0.02916, forecast_price_p10=142.6, forecast_price_p50=147.5, forecast_price_p90=151.3, train_loss=0.00593, actual_price=148.1, actual_return=0.00772, hit=0.55, in_band=0.8, close_sq_error=8.232, close_abs_error=2.288, n=20, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 8 | not available | not available | not available | not available | not available | n_observations=156, n_train_windows=105, lookback=30, last_close=163.8, forecast_return_p10=-0.02674, forecast_return_p50=0.002626, forecast_return_p90=0.02713, forecast_price_p10=159.5, forecast_price_p50=164.3, forecast_price_p90=168.3, train_loss=0.005903, actual_price=163.7, actual_return=-0.0007704, hit=0.3913, in_band=0.913, close_sq_error=7.08, close_abs_error=2.195, n=23, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 9 | not available | not available | not available | not available | not available | n_observations=178, n_train_windows=127, lookback=30, last_close=150.2, forecast_return_p10=-0.0347, forecast_return_p50=-0.003789, forecast_return_p90=0.02231, forecast_price_p10=145, forecast_price_p50=149.6, forecast_price_p90=153.6, train_loss=0.005676, actual_price=149.5, actual_return=-0.004491, hit=0.5238, in_band=0.7143, close_sq_error=15.36, close_abs_error=2.978, n=21, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 10 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=142.5, lookback=30, last_close=139.3, forecast_return_p10=-0.03452, forecast_return_p50=-0.001107, forecast_return_p90=0.02508, forecast_price_p10=134.5, forecast_price_p50=139.2, forecast_price_p90=142.8, train_loss=0.005941, actual_price=139.3, actual_return=-0.0001045, hit=0.5, in_band=0.7, close_sq_error=12.01, close_abs_error=2.788, n=10, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | n_observations=112, n_train_windows=61, lookback=30, last_close=138, forecast_return_p10=-0.02976, forecast_return_p50=0.0011, forecast_return_p90=0.02561, forecast_price_p10=133.9, forecast_price_p50=138.1, forecast_price_p90=141.5, train_loss=0.006404, actual_price=137.9, actual_return=3.985e-05, hit=0.44, in_band=0.64, close_sq_error=13.93, close_abs_error=3.144, n=25, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 3 | not available | not available | not available | not available | not available | n_observations=156.5, n_train_windows=105.5, lookback=30, last_close=154.1, forecast_return_p10=-0.03041, forecast_return_p50=0.0007552, forecast_return_p90=0.02618, forecast_price_p10=149.4, forecast_price_p50=154.2, forecast_price_p90=158.1, train_loss=0.005837, actual_price=154.2, actual_return=0.0006622, hit=0.4844, in_band=0.8125, close_sq_error=10.16, close_abs_error=2.481, n=64, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |
| 4 | not available | not available | not available | not available | not available | n_observations=193.5, n_train_windows=142.5, lookback=30, last_close=139.3, forecast_return_p10=-0.03452, forecast_return_p50=-0.001107, forecast_return_p90=0.02508, forecast_price_p10=134.5, forecast_price_p50=139.2, forecast_price_p90=142.8, train_loss=0.005941, actual_price=139.3, actual_return=-0.0001045, hit=0.5, in_band=0.7, close_sq_error=12.01, close_abs_error=2.788, n=10, computed_at=2026-08-09T13:46:03.949110+00:00, run_id=66cd65f0749d |

## Status counts by time format
1D: status = ok: n=99 (of 99)
1D: direction = up: n=54 (of 99)
1D: direction = down: n=45 (of 99)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/tft`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/tft/66cd65f0749d` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

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

---

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

---

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

---

# shock_personality (AAPL) -- Shock Personality

**shock_personality (AAPL):** Post-shock behavioral characterization — gap_fill_rate, vol_persistence (real GARCH, vinu_tools.compute.risk.volatility), drift_persistence_days (sign-streak) and drift_mean_autocorr (mean lag-1-9 return autocorrelation, previously computed and discarded, now reported), each also split by news presence (has_news/nearest_news_days, previously computed and discarded, now surfaced per-shock). Every field includes sample size and confidence interval. Output: Shock personality results with confidence intervals

Real data covers 2022-02-24 to 2022-10-13 (231 days), 17 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `magnitude`, `z_score`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | not available (n=0) |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`magnitude`, `z_score`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| tuesday | not available | not available | not available | not available | not available | magnitude=1.257, z_score=1.235, n=4, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| wednesday | not available | not available | not available | not available | not available | magnitude=0.5344, z_score=0.9176, n=4, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| thursday | not available | not available | not available | not available | not available | magnitude=2.059, z_score=1.345, n=7, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| friday | not available | not available | not available | not available | not available | magnitude=2.95, z_score=2.95, n=2, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | magnitude=1.174, z_score=1.153, n=7, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 3 | not available | not available | not available | not available | not available | magnitude=1.033, z_score=2.063, n=2, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 4 | not available | not available | not available | not available | not available | magnitude=2.149, z_score=1.467, n=8, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | magnitude=-0.04628, z_score=-2.96, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 3 | not available | not available | not available | not available | not available | magnitude=0.02747, z_score=2.048, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 4 | not available | not available | not available | not available | not available | magnitude=1.926, z_score=2.524, n=7, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 5 | not available | not available | not available | not available | not available | magnitude=1.054, z_score=0.01363, n=2, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 6 | not available | not available | not available | not available | not available | magnitude=2.329, z_score=2.329, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 7 | not available | not available | not available | not available | not available | magnitude=3.176, z_score=3.176, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 8 | not available | not available | not available | not available | not available | magnitude=3.258, z_score=3.258, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 9 | not available | not available | not available | not available | not available | magnitude=-0.02715, z_score=-2.408, n=2, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 10 | not available | not available | not available | not available | not available | magnitude=3.2, z_score=3.2, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | magnitude=-0.009403, z_score=-0.4561, n=2, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 2 | not available | not available | not available | not available | not available | magnitude=1.792, z_score=2.002, n=10, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 3 | not available | not available | not available | not available | not available | magnitude=1.595, z_score=0.4045, n=4, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |
| 4 | not available | not available | not available | not available | not available | magnitude=3.2, z_score=3.2, n=1, computed_at=2026-08-09T13:29:48.537242+00:00, run_id=590edee8ed42 |

## Status counts by time format
1D: type = vol_spike: n=10 (of 17)
1D: type = gap: n=7 (of 17)
1D: has_news = False: n=17 (of 17)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/shock_personality`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/shock_personality/590edee8ed42` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# shock_clustering (AAPL) -- Shock Clustering

**shock_clustering (AAPL):** Identifies which watchlist peers tend to shock together with this symbol: co-shock rate (did the peer also register its own shock within +/-1 trading day) plus shock-day Pearson correlation with a bootstrapped 95% CI, computed only on the anchor's own shock-date subset -- not a generic, unconditional correlation (that redundant, less rigorous version was dropped; see compute.py's module docstring for the corrected-bug history). peer_relative_strength (angle 21) already covers general rolling correlation between watchlist peers. Output: Shock cluster membership for the symbol

Real data covers 2022-02-24 to 2022-10-13 (231 days), 17 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `z`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | not available (n=0) |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`z`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| tuesday | not available | not available | not available | not available | not available | z=1.235, n=4, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| wednesday | not available | not available | not available | not available | not available | z=0.9176, n=4, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| thursday | not available | not available | not available | not available | not available | z=1.345, n=7, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| friday | not available | not available | not available | not available | not available | z=2.95, n=2, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | z=1.153, n=7, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 3 | not available | not available | not available | not available | not available | z=2.063, n=2, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 4 | not available | not available | not available | not available | not available | z=1.467, n=8, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | z=-2.96, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 3 | not available | not available | not available | not available | not available | z=2.048, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 4 | not available | not available | not available | not available | not available | z=2.524, n=7, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 5 | not available | not available | not available | not available | not available | z=0.01363, n=2, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 6 | not available | not available | not available | not available | not available | z=2.329, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 7 | not available | not available | not available | not available | not available | z=3.176, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 8 | not available | not available | not available | not available | not available | z=3.258, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 9 | not available | not available | not available | not available | not available | z=-2.408, n=2, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 10 | not available | not available | not available | not available | not available | z=3.2, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | z=-0.4561, n=2, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 2 | not available | not available | not available | not available | not available | z=2.002, n=10, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 3 | not available | not available | not available | not available | not available | z=0.4045, n=4, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |
| 4 | not available | not available | not available | not available | not available | z=3.2, n=1, computed_at=2026-08-09T13:29:48.501587+00:00, run_id=e75971c27358 |

## Status counts by time format
1D: trigger = range: n=10 (of 17)
1D: trigger = gap: n=7 (of 17)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/shock_clustering`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/shock_clustering/e75971c27358` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# news_price_causality_impact (AAPL) -- news_price_causality_impact

**news_price_causality_impact (AAPL):**

Table columns = candle/bar time resolution (declared time formats: 1D). Each cell states `ticker_count`, `ts`, `sentiment_score`, `abnormal_return_30m`, `car_1h`, `ar_p_value`, `computed_at`, `novelty_score`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1D |
|---|---|
| closed | ticker_count=2.022, ts=1.674e+09, sentiment_score=0.9556, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9343, n=45, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| london | ticker_count=1.93, ts=1.674e+09, sentiment_score=0.6279, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9187, n=43, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| ny_premarket | ticker_count=2.238, ts=1.674e+09, sentiment_score=1.524, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9438, n=21, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| ny_regular | ticker_count=2.163, ts=1.674e+09, sentiment_score=0.3023, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.8805, n=43, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| ny_afterhours | ticker_count=1.4, ts=1.674e+09, sentiment_score=1.2, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9735, n=5, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |

## Breakdown by calendar tag

Same fields as the session table above (`ticker_count`, `ts`, `sentiment_score`, `abnormal_return_30m`, `car_1h`, `ar_p_value`, `computed_at`, `novelty_score`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1D |
|---|---|
| monday | ticker_count=1.966, ts=1.675e+09, sentiment_score=1.103, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9456, n=29, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| tuesday | ticker_count=2.125, ts=1.674e+09, sentiment_score=1.312, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9219, n=32, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| wednesday | ticker_count=1.645, ts=1.674e+09, sentiment_score=1.129, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9389, n=31, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| thursday | ticker_count=2.2, ts=1.674e+09, sentiment_score=0.1333, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9015, n=30, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| friday | ticker_count=2.417, ts=1.674e+09, sentiment_score=0.4583, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.8593, n=24, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| saturday | ticker_count=1.667, ts=1.674e+09, sentiment_score=-0.3333, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9414, n=3, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| sunday | ticker_count=2, ts=1.675e+09, sentiment_score=-0.25, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9467, n=8, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1D |
|---|---|
| 2 | ticker_count=2.167, ts=1.673e+09, sentiment_score=0.5833, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9323, n=36, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| 3 | ticker_count=2.346, ts=1.674e+09, sentiment_score=0.8462, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9037, n=52, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| 4 | ticker_count=1.711, ts=1.675e+09, sentiment_score=0.7333, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9161, n=45, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |
| 5 | ticker_count=1.833, ts=1.675e+09, sentiment_score=0.9583, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9298, n=24, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |

### month (real calendar month number, 1-12)

| month | 1D |
|---|---|
| 1 | ticker_count=2.045, ts=1.674e+09, sentiment_score=0.7707, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9178, n=157, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |

### quarter (real calendar quarter, 1-4)

| quarter | 1D |
|---|---|
| 1 | ticker_count=2.045, ts=1.674e+09, sentiment_score=0.7707, abnormal_return_30m=0, car_1h=0, ar_p_value=1, computed_at=1.786e+09, novelty_score=0.9178, n=157, computed_at=2026-08-09T13:46:27.484223+00:00, run_id=bb733f4638a4 |

## Status counts by time format
1D: type = impact: n=157 (of 157)
1D: is_primary = True: n=100 (of 157)
1D: is_primary = False: n=57 (of 157)
1D: sentiment = NEUTRAL: n=76 (of 157)
1D: sentiment = BULLISH: n=61 (of 157)
1D: sentiment = BEARISH: n=20 (of 157)
1D: impact_label = low: n=157 (of 157)
1D: ar_significant = False: n=157 (of 157)
1D: ar_model = none: n=157 (of 157)
1D: analysis_at = 2026-08-09T13:46:18.229320+00:00: n=157 (of 157)
1D: angle = news_price_causality: n=157 (of 157)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/news_price_causality_impact`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/news_price_causality_impact/bb733f4638a4` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# news_price_causality_aggregate (AAPL)

no completed real run found yet.

---

# peer_relative_strength (AAPL) -- Peer Relative Strength

**peer_relative_strength (AAPL):** Measures how a symbol performs relative to its watchlist peer basket over time using rolling correlation and relative (excess) returns. Stands apart from shock_clustering (which only answers "which symbols shock together on shock dates") by computing peer co-movement and relative strength as a continuous, windowed signal across the full requested range. Output: Rolling peer correlation and excess-return rows per sampled bar: date, peer_symbol, correlation (63-day rolling), relative_return_20d.

Real data covers 2022-04-04 to 2023-01-12 (283 days), 80 real steps across 1 real time format(s).

Table columns = candle/bar time resolution (declared time formats: 1min, 5min, 15min, 1H, 4H, 1D). Each cell states `correlation`, `relative_return_20d`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | not available (n=0) |
| london | not available | not available | not available | not available | not available | not available (n=0) |
| ny_premarket | not available | not available | not available | not available | not available | not available (n=0) |
| ny_regular | not available | not available | not available | not available | not available | not available (n=0) |
| ny_afterhours | not available | not available | not available | not available | not available | not available (n=0) |

## Breakdown by calendar tag

Same fields as the session table above (`correlation`, `relative_return_20d`, plus `n`/`computed_at`/`run_id`), grouped instead by a real calendar tag every step already carries: `day_of_week` (real weekday name of the bar), `week_of_month` (1-5, which real calendar week of that month the bar falls in), `month` (real calendar month number, 1-12), `quarter` (real calendar quarter, 1-4). Unlike the session table, only real observed values become a row here -- there is no fixed universe of weeks/months/quarters to pre-list, so a value that never occurs in this run's real data is simply absent, not shown as `not available`.

### day_of_week (real weekday name of the bar)

| day_of_week | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| monday | not available | not available | not available | not available | not available | correlation=0.4323, relative_return_20d=-0.007899, n=26, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| tuesday | not available | not available | not available | not available | not available | correlation=0.3907, relative_return_20d=0.0303, n=20, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| wednesday | not available | not available | not available | not available | not available | correlation=0.4763, relative_return_20d=0.0495, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| thursday | not available | not available | not available | not available | not available | correlation=0.4412, relative_return_20d=0.05769, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| friday | not available | not available | not available | not available | not available | correlation=0.6013, relative_return_20d=0.04032, n=18, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.4337, relative_return_20d=0.02634, n=18, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 2 | not available | not available | not available | not available | not available | correlation=0.4479, relative_return_20d=0.01907, n=20, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 3 | not available | not available | not available | not available | not available | correlation=0.4733, relative_return_20d=0.02366, n=18, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 4 | not available | not available | not available | not available | not available | correlation=0.4891, relative_return_20d=0.03333, n=16, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 5 | not available | not available | not available | not available | not available | correlation=0.5135, relative_return_20d=0.02115, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.2699, relative_return_20d=0.1743, n=4, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 4 | not available | not available | not available | not available | not available | correlation=0.378, relative_return_20d=-0.06195, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 5 | not available | not available | not available | not available | not available | correlation=0.4692, relative_return_20d=0.03741, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 6 | not available | not available | not available | not available | not available | correlation=0.5685, relative_return_20d=-0.02705, n=10, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 7 | not available | not available | not available | not available | not available | correlation=0.6311, relative_return_20d=0.02954, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 8 | not available | not available | not available | not available | not available | correlation=0.5808, relative_return_20d=0.06219, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 9 | not available | not available | not available | not available | not available | correlation=0.5153, relative_return_20d=-0.06236, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 10 | not available | not available | not available | not available | not available | correlation=0.4359, relative_return_20d=0.02249, n=10, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 11 | not available | not available | not available | not available | not available | correlation=0.3964, relative_return_20d=0.06596, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 12 | not available | not available | not available | not available | not available | correlation=0.2908, relative_return_20d=0.09572, n=8, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.2699, relative_return_20d=0.1743, n=4, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 2 | not available | not available | not available | not available | not available | correlation=0.4793, relative_return_20d=-0.01795, n=26, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 3 | not available | not available | not available | not available | not available | correlation=0.5757, relative_return_20d=0.009789, n=24, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |
| 4 | not available | not available | not available | not available | not available | correlation=0.3791, relative_return_20d=0.0584, n=26, computed_at=2026-08-09T13:46:27.579426+00:00, run_id=46e922be4298 |

## Status counts by time format
1D: analysis_at = 2026-08-09T13:46:21.366493+00:00: n=80 (of 80)
1D: angle = peer_relative_strength: n=80 (of 80)
1D: date = 2022-04-04: n=2 (of 80)
1D: date = 2022-04-11: n=2 (of 80)
1D: date = 2022-04-19: n=2 (of 80)
1D: date = 2022-04-26: n=2 (of 80)
1D: date = 2022-05-03: n=2 (of 80)
1D: date = 2022-05-10: n=2 (of 80)
1D: date = 2022-05-17: n=2 (of 80)
1D: date = 2022-05-24: n=2 (of 80)
1D: date = 2022-06-01: n=2 (of 80)
1D: date = 2022-06-08: n=2 (of 80)
1D: date = 2022-06-15: n=2 (of 80)
1D: date = 2022-06-23: n=2 (of 80)
1D: date = 2022-06-30: n=2 (of 80)
1D: date = 2022-07-08: n=2 (of 80)
1D: date = 2022-07-15: n=2 (of 80)
1D: date = 2022-07-22: n=2 (of 80)
1D: date = 2022-07-29: n=2 (of 80)
1D: date = 2022-08-05: n=2 (of 80)
1D: date = 2022-08-12: n=2 (of 80)
1D: date = 2022-08-19: n=2 (of 80)
1D: date = 2022-08-26: n=2 (of 80)
1D: date = 2022-09-02: n=2 (of 80)
1D: date = 2022-09-12: n=2 (of 80)
1D: date = 2022-09-19: n=2 (of 80)
1D: date = 2022-09-26: n=2 (of 80)
1D: date = 2022-10-03: n=2 (of 80)
1D: date = 2022-10-10: n=2 (of 80)
1D: date = 2022-10-17: n=2 (of 80)
1D: date = 2022-10-24: n=2 (of 80)
1D: date = 2022-10-31: n=2 (of 80)
1D: date = 2022-11-07: n=2 (of 80)
1D: date = 2022-11-14: n=2 (of 80)
1D: date = 2022-11-21: n=2 (of 80)
1D: date = 2022-11-29: n=2 (of 80)
1D: date = 2022-12-06: n=2 (of 80)
1D: date = 2022-12-13: n=2 (of 80)
1D: date = 2022-12-20: n=2 (of 80)
1D: date = 2022-12-28: n=2 (of 80)
1D: date = 2023-01-05: n=2 (of 80)
1D: date = 2023-01-12: n=2 (of 80)
1D: peer_symbol = JNJ: n=40 (of 80)
1D: peer_symbol = TSLA: n=40 (of 80)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/peer_relative_strength`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/peer_relative_strength/46e922be4298` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# peer_relative_strength_forward_validation (AAPL) -- peer_relative_strength_forward_validation

**peer_relative_strength_forward_validation (AAPL):**

Table columns = candle/bar time resolution (declared time formats: 1D). Each cell states `n_rows`, `forward_5d_corr`, `forward_5d_p_value`, `forward_5d_ci_lower`, `forward_5d_ci_upper`, `forward_5d_sample_size`, `forward_10d_corr`, `forward_10d_p_value`, `forward_10d_ci_lower`, `forward_10d_ci_upper`, `forward_10d_sample_size`, `forward_20d_corr`, `forward_20d_p_value`, `forward_20d_ci_lower`, `forward_20d_ci_upper`, `forward_20d_sample_size`, plus `n` (how many real steps that value is based on), or `not available` when that (session, time format) combination has no real stored run yet.

All times below are UTC. Session row labels, as fixed UTC hour ranges (New York shifts with US daylight saving; London/closed do not):
- `closed` = 00:00-07:00 UTC
- `london` = 07:00-13:00 UTC
- `ny_premarket` = 13:00-13:30 UTC (DST) / 13:00-14:30 UTC (non-DST)
- `ny_regular` = 13:30-20:00 UTC (DST) / 14:30-21:00 UTC (non-DST) -- NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00-24:00 UTC (DST) / 21:00-24:00 UTC (non-DST)

| session | 1D |
|---|---|
| closed | not available (n=0) |
| london | not available (n=0) |
| ny_premarket | not available (n=0) |
| ny_regular | not available (n=0) |
| ny_afterhours | not available (n=0) |

## Status counts by time format
1D: peer_symbol = JNJ: n=4 (of 8)
1D: peer_symbol = TSLA: n=4 (of 8)
1D: quarter_key = 2022-Q2: n=2 (of 8)
1D: quarter_key = 2022-Q3: n=2 (of 8)
1D: quarter_key = 2022-Q4: n=2 (of 8)
1D: quarter_key = 2023-Q1: n=2 (of 8)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/peer_relative_strength_forward_validation`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/peer_relative_strength_forward_validation/7a96385a5805` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---

# pnl_attribution (AAPL) -- PnL Attribution

**pnl_attribution (AAPL):** Realized-trade PnL statistics per symbol -- win rate, average win/loss, trade count -- computed from Phase 6 (vinu-live) execution logs. Every field includes sample size and confidence interval. Deviates from the standard runner-driven angle pattern: its natural input is closed positions/fills, not price bars, so it is push-fed via POST /pnl-attribution/{symbol}/record (Phase 7's feedback loop) rather than pulled by AngleRunner from bars/news. `compute()` still exists with the standard signature so a generic `/run/{ticker}` sweep doesn't error, but it is a documented no-op there -- real population happens through the ingest path (`pnl_attribution_ingest.py`), which calls `aggregate_pnl_attribution` directly and writes via `AngleStorage.write()`. Output: PnL attribution results with confidence intervals

## Status counts by time format
1D: analysis_at = 2026-08-09T13:46:27.473336+00:00: n=1 (of 1)
1D: angle = pnl_attribution: n=1 (of 1)
1D: status = no_data: n=1 (of 1)
1D: closed_positions_json = []: n=1 (of 1)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/pnl_attribution`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/pnl_attribution/fe30e899281f` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._

---
