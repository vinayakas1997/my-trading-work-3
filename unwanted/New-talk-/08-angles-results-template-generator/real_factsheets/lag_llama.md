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