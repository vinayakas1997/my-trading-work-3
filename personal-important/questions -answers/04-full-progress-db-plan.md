# Full Progress DB Plan - Per Ticker + Reset (2026-09-08)

Simple English. One place to see Full status.

## Goal
When you ask how much finished, we read one DB. No need to check 5 places.

## Counts per ticker per timeframe (expected)
- 1min = 28 angles (all support 1min)
- 5min = 28 angles
- 15min = 28 angles
- 1H = 28 angles (dlinear 1H 8309 ok, trend works on 1H)
- 4H = 28 angles
- 1D = 27 angles (27/27 done, not 27/28. trend has no 1D by design)
- 1W, 1M, 6M = 1 angle only (backtesting_44_metrics has extra formats)

Total one ticker all formats where supported = 167 + 3 = 170 runs.
3 tickers AAPL,MSFT,NVDA = 510 runs for full coverage.
Today: 1D 27 done, 1H partly done, total 93 for 2022 window.

## DB choice
File: `data/agent/full_progress.db`
Table: `full_progress`

Columns:
- ticker TEXT (AAPL, MSFT, NVDA)
- time_format TEXT (1min,5min,15min,1H,4H,1D)
- angle_name TEXT (kronos, dlinear, arima...)
- stage TEXT (0 watchlist,1 summary,2 triage,3 sweep,4 risk,5 capital,6 shadow,7 monitor)
- status TEXT (pending, running, done, error)
- run_id TEXT
- interval_from TEXT (2022-01-01)
- interval_to TEXT (2026-07-01)
- updated_at TEXT
- error TEXT

One row per ticker + format + angle + stage.
Example: AAPL 1D kronos stage1 done 2022_2026-07-01.
Example: AAPL 1D trend pending (not expected, skip for 1D).

## Tradeoff
1. Per ticker only (3 rows):
   Good: small, fast.
   Bad: cannot see which angle stuck. 27/27 hidden.

2. Per ticker+format+angle (170 rows per ticker):
   Good: clear. See 1D 27/27 done, 1H 12/28 running, dlinear error, trend skip correct.
   Bad: more rows, more writes. Still tiny and fast.
   Choice: Use this. Clear is better.

3. Reset auto every quarter (Q3 2026-07-01 to Q4 2026-10-01):
   Good: always fresh. New window 2022_2026-10-01 auto.
   Bad: recompute 500 runs every 3 months. Cost LLM time.
   Rule: Reset only when interval_to changes per quarters.py. Not every poll.
   Keep old done for old window. Set pending for new window.

4. Reset manual only when you say Full:
   Good: less cost.
   Bad: data gets old. New bars not analysed.
   Choice: Use auto on interval change. Best balance.

## How agents tick checkbox
- initial compute writes done/error per angle per format.
- screener writes summary done per ticker.
- research writes sweep iter 1/5 running/done per ticker.
- risk writes PEND done per ticker.
- capital writes ACTIVE done per ticker.
- shadow writes paper day 1/5 per ticker.
- monitor writes hold/exit per ticker.

## How to read status
Query: count done / expected per ticker per format.
Example answer:
- AAPL 1D 27/27 done
- AAPL 1H 12/28 running
- MSFT 1D 20/27 running
- NVDA sweep iter 2/5 running

## Reset rule
When `last_completed_period_end` changes (quarters.py), set:
- interval_from = VINU_STAGE1_START_DATE (2022-01-01)
- interval_to = new period end (2026-10-01)
- status = pending for new window
Old window rows stay done for history. Do not delete all.

## Next build steps (not done yet, plan only)
1. Create DB and table.
2. Add tick in angles_tool, scheduler_workers, research loop.
3. Add read API `GET /agent/full-progress/AAPL`.
4. Show in file `04-full-status.md` checkbox for you to read any time.
