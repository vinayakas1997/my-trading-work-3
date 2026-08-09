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