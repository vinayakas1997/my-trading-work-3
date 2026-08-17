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