# Full Pattern — Full Runbook (stage-by-stage trigger → response → store → TickerLedger ref_id)

> One real ticker (AAPL first) end-to-end, full window `2022-01-01`. Same table as ATS `04-ats-runbook` but now metrics are production-trustworthy and `what wil happen` includes promotion thresholds.

| # | Stage | Trigger (real) | Response you see | Store you confirm | `TickerLedger` row | What wil happen (why) |
|---|---|---|---|---|---|---|
| 0 | `watchlist_gate` | `RunLogTrigger` new `run_id` | `yes` → `SA` (not `next ticker`) | `TickerSummaryStore last_checked_run_id` | `stage=watchlist_gate event_type=changed` | Dedupe `has_existing_run()` |
| 1 | `summary_agent` | `get_all_angles(AAPL)` | summary + `agree/diverge` | `TickerSummaryStore` `source_run_id` today | `summary_refreshed` | Grounding `row_count>0` only |
| 2 | `planner_triage` | `PlannerTriage.check(AAPL)` | tier + prior_rejections + recipe | `HypothesisRegistry` consulted, K counter | `triage` | Shared K-cap |
| 3 | `sweep` | `run_sweep_candidate` | `rank_candidates` table + `completeness` + `PaperRehearsalResult` `rehearsal_from 7d` | `BacktestResult` | `sweep result + verdict` | Fail-closed <0.7; rehearsal `PASS/FAIL` with note |
| 4 | `risk_gatekeeper` | `get_portfolio` | `APPROVED` + `approved_size` `fractional_kelly 0.25` | `PEND` `approved_size` | `APPROVED` vs `REJECTED → SIG` | Fit current exposure only |
| 5 | `capital_allocator` | `900s` batched `evaluate-batch` | `candidates` `funded` + `replace_recommendations` + `composition_view gaps` → `mark_active` or `PENDBLOCK` (Kill + throttle 10/sec) | `ACTIVE`/`PENDBLOCK` | `funded/PENDBLOCK/rebalance_requested` | Batch avoids first-come; re-check exposure + NEW-vs-NEW corr |
| 6 | `live_shadow` | `shadow-worker` `BENCHING→ACTIVE` | `paper_sharpe` vs backtest, `degradation<=0.5` | `performance_store daily_returns` | `shadow` ledger separate | Paper twin `min_paper_days=5` |
| 7 | `monitor` | `cycle()` / `cycle_shock_batch(5)` | `hold` vs `invalidation_exit` vs `rebalance_honored` (sole authority, declines if `>5% gain`) | `trade_plan_book.db` + `HR` on close | `check, decay, close-out why` | Shock prioritized; rebalance never closes directly |

After full run for AAPL, repeat `MSFT` then `NVDA` same table, same `test_run_id` but different `ticker` — `UNIQUE(test_run_id,ticker,stage)` resume.
