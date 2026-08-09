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