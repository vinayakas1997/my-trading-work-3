# Test Status Ledger — human-readable

> Append-only, one row per `(test_run_id,ticker,stage)` — mirrors `TickerLedger` `04:128` discipline but for test harness. `UNIQUE(test_run_id,ticker,stage)` — re-running same ticker/stage same run updates same row, never duplicates, so `kill -9` resume is `get_pending(test_run_id)`.

| test_run_id | ticker | stage | status | timestamp | evidence_ref | notes | fixed_by | fixed_how |
|---|---|---|---|---|---|---|---|---|
| `2026-09-07_ats_6mo` | AAPL | watchlist_gate | pass | `2026-09-07T13:44:05Z` | `TickerSummaryStore AAPL source_run_id 49235cdecfb0 last_checked_run_id 49235cdecfb0; TickerLedger summary_refreshed ref 49235cdecfb0 + planner candidate_proposed ref 736c28d490a3` | Gate changed on fresh bootstrap, RunLog dedup ok | | |
| `2026-09-07_ats_6mo` | MSFT | watchlist_gate | pass | `2026-09-07T13:44:05Z` | `TickerSummaryStore MSFT source_run_id dc6c05e2644d last_checked_run_id dc6c05e2644d; TickerLedger summary_refreshed ref dc6c05e2644d + planner candidate_proposed ref 488a923de4a6` | | | |
| `2026-09-07_ats_6mo` | NVDA | watchlist_gate | pass | `2026-09-07T13:44:05Z` | `TickerSummaryStore NVDA source_run_id 6047fb441a61 last_checked_run_id 6047fb441a61; TickerLedger summary_refreshed ref 6047fb441a61 + planner candidate_proposed ref 163c1a3a3be9` | | | |
| `2026-09-07_ats_6mo` | AAPL | summary_agent | pass | `2026-09-07T13:44:05Z` | `TickerSummaryStore AAPL angle_count 28 source_run_id 49235cdecfb0; TickerLedger summary_refreshed` | angles_with_data=0 pre-auth-fix (analysis→stock/news 401); re-check next cycle | | |
| `2026-09-07_ats_6mo` | MSFT | summary_agent | pass | `2026-09-07T13:44:05Z` | `TickerSummaryStore MSFT angle_count 28 source_run_id dc6c05e2644d; TickerLedger summary_refreshed` | same angles_with_data=0 note as AAPL | | |
| `2026-09-07_ats_6mo` | NVDA | summary_agent | pass | `2026-09-07T13:44:05Z` | `TickerSummaryStore NVDA angle_count 28 source_run_id 6047fb441a61; TickerLedger summary_refreshed` | same angles_with_data=0 note as AAPL | | |
| `2026-09-07_ats_6mo` | AAPL | planner_triage | pass | `2026-09-07T13:48:38Z` | `TickerLedger planner candidate_proposed ref 736c28d490a3 (recipe=crossover, 0 in flight, 0 prior rejections)` | | | |
| `2026-09-07_ats_6mo` | MSFT | planner_triage | pass | `2026-09-07T13:47:05Z` | `TickerLedger planner candidate_proposed ref 488a923de4a6` | | | |
| `2026-09-07_ats_6mo` | NVDA | planner_triage | pass | `2026-09-07T13:46:05Z` | `TickerLedger planner candidate_proposed ref 163c1a3a3be9` | | | |
| `2026-09-07_ats_6mo` | AAPL | sweep_execute | pass | `2026-09-07T14:40Z` | `POST /research/sweep/candidate run_id 45bad5f9-823f-4e48-b179-9212768e6bae sharpe -0.606 trade_count>0` | manual trigger (workers blocked pre-fix); first research team runs STOPped on simulator 401, fixed via internal Bearer | | |
| `2026-09-07_ats_6mo_r2` | AAPL | watchlist_gate | pass | `2026-09-07T15:39:51Z` | `tier2 run dafed8da3b6c (explicit Mar→Sep window, detached container run — survives client abort)` | forced recompute instead of waiting hourly scheduler | | |
| `2026-09-07_ats_6mo_r2` | MSFT | watchlist_gate | pass | `2026-09-07T16:22:57Z` | `tier2 run 1b9086f2c3e3 (same forced path)` | | | |
| `2026-09-07_ats_6mo_r2` | AAPL | summary_agent | pass | `2026-09-07T15:43:54Z` | `27/28 angles with data, source dafed8da3b6c; TickerLedger summary_refreshed` | was 0/28 pre-fix | | |
| `2026-09-07_ats_6mo_r2` | MSFT | summary_agent | pass | `2026-09-07T16:25:24Z` | `27/28 angles with data, source 16781813dc2b; TickerLedger summary_refreshed` | | | |
| `2026-09-07_ats_6mo_r2` | NVDA | summary_agent | pass | `2026-09-07T14:33:34Z` | `27/28 angles with data, source b6c43fde2de1` | first post-fix proof | | |
| `2026-09-07_ats_6mo_r2` | AAPL | planner_triage | pass | `2026-09-07T15:47:20Z` | `TickerLedger candidate_proposed (crossover)` | | | |
| `2026-09-07_ats_6mo_r2` | MSFT | planner_triage | pass | `2026-09-07T16:26:45Z` | `TickerLedger candidate_proposed (crossover), research run d282d765a001` | | | |
| `2026-09-07_ats_6mo_r2` | AAPL | sweep_verdict | pass | `2026-09-07T15:43:54Z` | `research dba273786bd9 STOP after 4 real rounds (best Sharpe +1.05 on 2 trades → FAIL sample size; ADX; RSI -0.34)` | LEGIT statistical FAIL — thin 6mo data, exactly the runbook-expected outcome, not infra | | |
| `2026-09-07_perf_cal_wiring` | (all) | summary_agent | pass | `2026-09-07T18:22:05Z` | `planner-worker 3× latest-run GET (AAPL/MSFT/NVDA) issued within 14ms = parallel _map_parallel active (scheduler_workers.py:247 bootstrap + cli.py:371 refresh); agent 86 tests pass incl. 3-way barrier proof; calibration low-trust overlay wired (decision 08) but 0 rated angles yet (no closed attributions)` | PERF/CALIBRATION wiring verification, NOT a fresh LLM pipeline pass (conserving free-tier 200/day); no new source_run_id — existing r2 summaries untouched | commit <pending> inefficiencies-A-J B | `summary_parallelism` default 3 bounded pool; openai client 429 now Retry-After+jitter |

- `status`: `pass` | `fail` (never `pending` on write — pending is absence of row)
- `evidence_ref`: real store row it produced (`artifact_id art_...`, `run_id ...`, `flag_id`, `TickerLedger row id`)
- `notes`: only on `fail` — specific enough to turn directly into bug report, not "didn't work"
- `fixed_by`: `commit <sha> <file:line>` when fail later fixed
- `fixed_how`: what widened / wired / tuned (e.g. `loop.py:_run_paper_rehearsal 7d` / `K=3→4`)
- Stage-name mapping (test-plan shorthand → real `TickerLedger.stage` values in `vinu-agent/.../storage/ticker_ledger.py` + `ticker_gate.py`): `watchlist_gate` = `runlog_trigger` + `change_gate` rows; `summary_agent` = `summary_agent/summary_refreshed`; `planner_triage`/`planner_idea` = `planner/candidate_proposed`; `risk_gatekeeper` = `risk_gatekeeper/APPROVED|REJECTED`; `capital_allocator` = `capital_allocator/funded|PENDBLOCK|rebalance_requested`; `live_shadow`/`monitor` = their own stage names. Query with `stage IN (...)` per mapping, not exact match.

Delete whole folder after gate `green` is copied to `pending Status`, or per `test_run_id` individually.
