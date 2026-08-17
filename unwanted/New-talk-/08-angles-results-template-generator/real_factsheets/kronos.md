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