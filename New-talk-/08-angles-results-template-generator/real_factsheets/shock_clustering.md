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