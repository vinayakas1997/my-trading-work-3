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