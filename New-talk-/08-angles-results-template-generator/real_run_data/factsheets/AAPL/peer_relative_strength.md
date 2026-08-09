# peer_relative_strength (AAPL) -- Peer Relative Strength

**peer_relative_strength (AAPL):** Measures how a symbol performs relative to its watchlist peer basket over time using rolling correlation and relative (excess) returns. Stands apart from shock_clustering (which only answers "which symbols shock together on shock dates") by computing peer co-movement and relative strength as a continuous, windowed signal across the full requested range. Output: Rolling peer correlation and excess-return rows per sampled bar: date, peer_symbol, correlation (63-day rolling), relative_return_20d.

Real data covers 2023-02-02 to 2023-05-15 (102 days), 30 real steps across 1 real time format(s).

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
| monday | not available | not available | not available | not available | not available | correlation=0.06155, relative_return_20d=0.01625, n=12, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| thursday | not available | not available | not available | not available | not available | correlation=0.3967, relative_return_20d=-0.08707, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| friday | not available | not available | not available | not available | not available | correlation=0.3019, relative_return_20d=0.03601, n=12, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

### week_of_month (1-5, which real calendar week of that month the bar falls in)

| week_of_month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.2603, relative_return_20d=0.02135, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 2 | not available | not available | not available | not available | not available | correlation=0.2113, relative_return_20d=-0.004831, n=8, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 3 | not available | not available | not available | not available | not available | correlation=0.1805, relative_return_20d=-0.001959, n=8, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 4 | not available | not available | not available | not available | not available | correlation=0.2577, relative_return_20d=0.01599, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 5 | not available | not available | not available | not available | not available | correlation=0.2499, relative_return_20d=-0.03248, n=2, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

### month (real calendar month number, 1-12)

| month | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 2 | not available | not available | not available | not available | not available | correlation=0.3863, relative_return_20d=-0.06845, n=8, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 3 | not available | not available | not available | not available | not available | correlation=0.2913, relative_return_20d=0.04574, n=10, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 4 | not available | not available | not available | not available | not available | correlation=0.1636, relative_return_20d=-0.03462, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 5 | not available | not available | not available | not available | not available | correlation=-0.04054, relative_return_20d=0.06712, n=6, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

### quarter (real calendar quarter, 1-4)

| quarter | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| 1 | not available | not available | not available | not available | not available | correlation=0.3335, relative_return_20d=-0.005015, n=18, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |
| 2 | not available | not available | not available | not available | not available | correlation=0.06155, relative_return_20d=0.01625, n=12, computed_at=2026-08-09T14:00:23.930042+00:00, run_id=026004a67db0 |

## Status counts by time format
1D: analysis_at = 2026-08-09T14:00:17.871939+00:00: n=30 (of 30)
1D: angle = peer_relative_strength: n=30 (of 30)
1D: date = 2023-02-02: n=2 (of 30)
1D: date = 2023-02-09: n=2 (of 30)
1D: date = 2023-02-16: n=2 (of 30)
1D: date = 2023-02-24: n=2 (of 30)
1D: date = 2023-03-03: n=2 (of 30)
1D: date = 2023-03-10: n=2 (of 30)
1D: date = 2023-03-17: n=2 (of 30)
1D: date = 2023-03-24: n=2 (of 30)
1D: date = 2023-03-31: n=2 (of 30)
1D: date = 2023-04-10: n=2 (of 30)
1D: date = 2023-04-17: n=2 (of 30)
1D: date = 2023-04-24: n=2 (of 30)
1D: date = 2023-05-01: n=2 (of 30)
1D: date = 2023-05-08: n=2 (of 30)
1D: date = 2023-05-15: n=2 (of 30)
1D: peer_symbol = JNJ: n=15 (of 30)
1D: peer_symbol = TSLA: n=15 (of 30)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/peer_relative_strength`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/peer_relative_strength/026004a67db0` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._