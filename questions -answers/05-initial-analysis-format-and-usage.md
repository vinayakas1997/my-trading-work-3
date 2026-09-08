# Initial Analysis - Format, Storage and Usage (2026-09-08)

Simple English. One place to understand Full initial result.

## 1. How result is stored? Do we have specific format? Yes.
Where: `data/initial-analysis/vinu_initial_analysis_runs.db` RunLog + AngleStorage per angle per format.
Window: `2022-01-01 to 2026-07-01` tier2 official, tier3 v1 fetch for Full.

Format one row per angle per format:
- symbol, analysis_at, angle, status ok/no_data, n_observations
- Example 1D kronos: n=1125, predicted_next_close 290.15, direction up
- Example 1H dlinear: n=8309, forecast_price 277.47, train_loss 0.016
- Example arima: order, AIC, forecast + 95% interval
- RunLog fields: symbol, angle_name, run_id, started_at, analysis_from 2022-01-01,
  analysis_until 2026-07-01, stored_at, status completed/error, row_count 1,
  granularity 1D/1H, tier tier2/tier3. Today 93 total for 2022.

How to read:
- `GET /analysis/angle/{name}/{ticker}` tier2
- `GET /v1/stage1/vinu-initial-analysis/fetch/{ticker}/1day/2022-01-01_2026-07-01/{angle}` tier3
- `get_all_angles` reads all 27/27 1D ok, then screener writes summary.

## 2. Is my format efficient? Yes or no? Yes.
One row per angle per format is efficient for our use.
- 1D kronos 1 row, 1H dlinear 1 row, tiny files.
- `get_all_angles` reads one angle one file, fast. No full scan.
- `has_existing_run` dedupe, no recompute if same window.
Not efficient only if you query all tickers all formats together (170x3 files, many opens).
We do not need bulk today. So yes, efficient for Full 0 to 7.

## 3. Is it implemented for all angles? Yes or no? Yes.
Yes, for all 28 where format supports.
- 1D = 27/27 done (trend has no 1D by design, only 1min-4H).
- 1H,4H,1min,5min,15min = 28/28 when run (dlinear 1H ok, trend 1H ok).
- 1W,1M,6M = 1 angle only (backtesting_44_metrics extra).
- Code ready for all 28. Today 1D+1H partly done (93 total 2022), not yet all 6 formats x3 tickers (501 runs), but format supports all.

Rule: say 27/27 for 1D done, not 27/28. Say 28/28 for 1H done.

## 4. Anyone wants info, will access summary? Yes or no? Yes.
Yes. Anyone reads summary first.
Summary = `TickerSummaryStore` 27/27 1D, agree/diverge, kronos up 1125.
Planner, research, risk, UI all read summary first for quick view.
If need detail (kronos 290.15, dlinear 277.47), then read raw angle API after summary.

Both agents and UI user use summary as entry.

## 5. Down line, is full analysis properly used in necessary steps?
Used properly today:
- Step 1 Screener summary_agent: get_all_angles 27/27 ok -> summary. Yes.
- Step 2 Planner triage: reads summary tier + K-cap. Yes.
- Step 8 Shadow: reads via calibration after paper. Yes when ACTIVE comes.

Not properly used today, need fix there:
- Step 3 idea_generator: 27 ready but angles_used [] before. Fixed wiring to tier3 2022 ok, need prompt mature.
- Step 3 backtest_runner: only 1 iter crossover always, not 5 + PBO. Need vectorbt fast + diverse.
- Step 4 risk_critic: STOP due to Step 3 gaps. Will fix when Step 3 fixed.
- Steps 6,7,9 risk, capital, monitor: blocked, no PEND/ACTIVE. Wired but idle. Will run when PASS comes.

So 1-2,5-9 wired yes. 3-4 gap blocks 6-9. Fix 3-4 first.
