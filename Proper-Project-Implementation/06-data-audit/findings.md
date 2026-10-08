# Data audit findings

Running list. Status is `FIXED` (problem-log entry and guard test), `OPEN` (reason given) or `QUESTION` (needs a decision from the user, nothing invented).

## news (pilot, 2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-N1 | wrong shape | The news service answers `{"count", "data": [...]}` with unix-second times. Two agent readers (`memory/sync_service.py` `sync_news`, `tools/trade_plan_tool.py` `_fetch_news`) looked for `results`/`articles`, so they saw "no articles" for every ticker: the agent's memory never held news and every trade plan said no news. Had they seen articles, the plan's date slice (`[:10]` on an integer) would have crashed. Their tests mocked a bare list. | FIXED: problem-log P63, guard `vinu-agent/tests/test_news_payload_shape.py` |
| DA-N2 | dead source | Feed `ap_top_news` has failed 252 of 252 polls with `http_403`. Nothing reads `feed_health`, so nobody is told. | FIXED: problem-log P66 (layer 1 of the news plan: health, automatic switch-off, read-out) |
| DA-N3 | thin data | 54,932 of 55,156 articles (99.6%) come from one provider (Benzinga). The 11 other sources give 224. No tier-1 source (Fed, SEC and similar) appears in the articles although their feeds poll fine. Last poll: 673 leads, 16 kept after the filter. | CORRECTED: live ingest is mixed-source (Benzinga 194, Investing.com 65, Seeking Alpha 54, CNBC 34, Bloomberg 20 in three days); the 99.6% was the 2023 backfill. The filter keeping 16 of 673 leads stands as a question (O24) |
| DA-N4 | computes nothing | Clustering gives 55,156 clusters for 55,156 articles; threads hold one article in 99.6% of cases. With one source there are no duplicates to group. `story_threads` and `thread_daily_snapshots` (112k rows) have no reader. | CORRECTED and FIXED: the groups were formed and the extra reports discarded before storing, not absent (P67, P68). Live: multi-source stories now exist |
| DA-N5 | empty by design | `finbert_score`/`finbert_label` are empty on all articles (the models container is dormant). The `news_price_causality` significance model lists `finbert_score` as a feature, so that feature is always empty. | OPEN, by design (O24) |
| DA-N6 | computed then dropped | `news_price_causality/correlation.py` builds `avg_impact` from a field `impact_label` that the news service does not send (it sends `impact`, upper-case), so it is always 0, and nothing reads `avg_impact`. | OPEN, small (O24) |
| DA-N7 | no reader | `entities_json` (people, countries) is filled on 29% of articles; nothing reads it. | OPEN (O24): entities now also sit in `story_facts` (layer 4) |
| DA-N8 | no reader | `ticker_daily_stats` (daily bullish/bearish/neutral count per ticker, 34,308 rows) and the routes `/news/stats/ticker`, `/news/high-impact`, `/news/latest`, `/news/watchlist/news`, `/news/threads/*` have no caller in any service. | QUESTION: should the screener or the portfolio read the daily mood? (O24) |
| DA-N9 | not used for decisions | News reaches strategy ideas only through the angle summaries in the research prompt, and the agent's trade-plan text. It does not reach the daily allocation, the live scheduler, the guards or the breaker. The `get_news` tool exists but no agent definition names it. | QUESTION: where should news be allowed to act? (O24) |
| DA-N10 | partial | Price reaction exists for 31% of articles (only for tickers that were requested), takes `tickers[0]` rather than the dominant ticker, and `dominance` is returned but unused. | OPEN, small (O24) |
| DA-N11 | wrong source of rows | The agent's two readers used `/news/search` (relevance order), so the plan's news section for AAPL showed headlines from 2023 and 2024. | FIXED with DA-N1 (P63): they use the newest-first ticker route |

## stock-price (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-S1 | no reader | `gap_count` (542,317 missing bars over 50 symbols) is only printed by reflection; nothing decides from it, and no one knows if the gaps are real holes or just thin extended-hours minutes on the IEX feed. | OPEN: needs a decision on what a gap should do (O25) |
| DA-S2 | stale field | `has_adj_data` is 0 for all 50 symbols although bars are requested with `adjustment=all`; nothing reads it. | OPEN, small (O25) |
| DA-S3 | unbounded | `ingest_log` gains about 72,000 rows a day (26 million a year) with no pruning; failure rows hold a 1-2 KB error each; one reader (reflection). `spread_snapshots` also never pruned. | OPEN (O25) |
| DA-S4 | no reader | `spread_snapshots` and `/stock/spread-stats` have no consumer (the simulator uses published figures, O10). | OPEN, by design for now (O25) |
| DA-S5 | wrong data, matters for 24h | Outside regular hours the quote has no valid two-sided price (real call: ask 0.0). The after-hours and overnight "spread statistics" are identical, so they are not a measured spread. The live spread guard fails open on a missing quote, so in pre-market, after-hours and overnight it protects nothing. | OPEN: tied to O3/O10; needs a feed with real extended-hours quotes or a rule for what to do without one (O25) |
| DA-S6 | not stored | Macro events (rate decisions, CPI, jobs) are pulled (`last_pull:economic` is set) but 0 rows exist and there is no Finnhub key among the secrets, so the event blackout can only ever see earnings. | QUESTION: is a macro blackout wanted, and is a Finnhub key to be added? (O25) |
| DA-S7 | single source | Only Alpaca (IEX) supplies bars; `provider_fallback_log` is empty because no second provider was ever used. A DNS outage on 2026-10-07 left 200 failed minutes. | OPEN, noted (O25) |

## screener (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-R1 | silent partial result | The ranker saved a "latest" ranking built from 20 of its 50 symbols after two candle chunks timed out, with no mark on the snapshot. The planner and the churn history then treat it as the full ranking. The cause is speed: a batch candle call costs about 2.5-3 s per symbol (measured: 20 daily symbols 62 s, 5 one-minute symbols 12 s), and the chunk budget is 30 s + 3 s per symbol. | OPEN, fix is in-scope and needs no decision: mark/refuse a partial ranking and keep the last full one (O26) |
| DA-R2 | history lost | Only the latest snapshot is kept (primary key `ranker_id`); 106 churn events are the only history, so nobody can later test whether the ranker predicts anything. | OPEN (O26) |
| DA-R3 | empty | No rule exists: the scan monitor, dry-run, history and watch-audit code produce nothing. | QUESTION: is the condition-alert feature wanted? (O26) |
| DA-R4 | not used for decisions | The ranking does not reach sizing, entry or the portfolio; the research size tilt is switched off (no ranker id configured). The planner uses only the symbol list, so negative-scoring names are "top". | QUESTION: should the score matter (a floor, or a size tilt)? (O26) |
| DA-R5 | stock-api slow and once restarted | Batch candle reads are slow (see DA-R1). During my timing test the stock-api container exited with code 0 once (a 20-symbol one-minute batch) and restarted; a smaller repeat did not reproduce it, cause not established. | OPEN: investigate (O26) |

## initial-analysis (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-I1 | cost without a reader | `peer_relative_strength` is 254 MB of the 355 MB store (72%), 22.9 million rows, 83 s per run, and is named only inside the agent, not in research, live or portfolio. | QUESTION: keep, thin out, or drop? (O27) |
| DA-I2 | seven angles named only in the agent | drawdown_deep_dive, exponential_smoothing, kalman_filters, arima, trend_session_structure, search_trends and peer_relative_strength are produced for 50 symbols and 9 bar sizes but are not used by research, live or portfolio. | QUESTION: which of these should feed decisions? (O27) |
| DA-I3 | unused tracker | `angle_run_status` (retries, heartbeat) has no table in the live databases; `run_log.db` and `meta.db` are empty stray files. | OPEN, small (O27) |
| DA-I4 | upstream slowness | 1-minute angle runs fail on stock-api read timeouts (same slowness as DA-R1). | OPEN with DA-R1 (O27) |
| DA-I5 | old runs kept | Every run's files are kept (5,441 files for 5,452 runs); only the newest is read. | OPEN, small: decide retention (O27) |
| DA-I6 | routes with no caller | `/events`, `/story`, `/coverage`, `/manifest`, `/factsheet` have no caller in any other service. | OPEN, small (O27) |
| DA-I7 | stale window | The newest analysis files end on 2026-10-01 (file names `..._261001`), while prices are current to today. | QUESTION: what refreshes angles, and how often? (O27) |

## research (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-X1 | computed then dropped | 24 of 44 research reports said "Fix the error above" without the error: the crash cause sat in the critique's reasoning and the report printed only suggestions (from an unordered set). | FIXED: problem-log P64, guard `vinu-research/tests/test_report.py::TestCrashCauseReachesTheReport` |
| DA-X2 | result, not defect | Of 44 runs: 24 code crashes, 20 stopped by significance tests (block-bootstrap 19, BCa 17, bootstrap interval 17, placebo 17, price-path 11, trade-permutation 11, walk-forward 9); 15 had positive Sharpe, best 1.30; none passed. Input for the "why strategies do not pass" step. | NOTED |
| DA-X3 | writer quality | 55% of candidate strategies do not run at all (for example a library `ta` that does not exist in the sandbox). The cause was invisible until DA-X1. | OPEN: read the causes now that they are stored (O28) |
| DA-X4 | caller/recipe mismatch | 59% of sweep grid points fail for caller-side reasons: unknown recipe names (`ma_crossover`, `sma_crossover`), unknown params, no `fast_period` to substitute, class not found, and 87 with no weight data. | OPEN: agent and research must share one recipe list (O28) |
| DA-X5 | tables that should have rows | After 44 runs `strategy_validations`, `iteration_checkpoints` and `telemetry.steps` are empty; `research_runs.db` is an empty stray file. | OPEN (O28) |
| DA-X6 | drill leftovers | Two of the three artifacts are from my own drill (SPY, AAPL), DISABLED. | NOTED |
| DA-X7 | thin evidence | `signal_triggers` has 8,188 rows but one distinct must-condition for all 50 symbols, so the evidence cannot compare conditions. | QUESTION: which conditions should be recorded? (O28) |
| DA-X8 | status without a basis | 5 hypotheses are "validated" while no strategy has passed validation. | QUESTION: what makes a hypothesis validated? (O28) |

## simulator and strategy (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-M1 | mismatch with the mandate | 1,019 of 1,022 simulator runs allowed shorting (`VINU_RESEARCH_ALLOW_SHORT` defaults to true; the shadow backtester and tool defaults are true too) while the mandate is long-only. Candidates are validated on a payoff the system cannot take. | OPEN, chain C2: make the research/simulator default long-only (O29) |
| DA-M2 | empty | `simulation_catalog` has 0 rows; runs and files (52 MB, 5 files per run) are never pruned. | OPEN, small (O29) |
| DA-M3 | idle | The strategy service has 11 YAML strategies and has never evaluated one (`strategy_runs`, `weights`, `precondition_state` all empty). | NOTED: follows from "no capital to YAML strategies" (P53) |
| DA-M4 | reads zeros | `news_aware_momentum` reads news effect from routes that return an empty placeholder for AAPL although 7,976 articles exist (chain C1). | FIXED at the source (chain C1, P70); the cached results of 36 symbols still need a re-run (O33) |

## portfolio (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-P1 | no reader, mixed bases | `allocation_history` (2 rows, from the 96,613-dollar paper era with YAML strategies) is read by nobody; `/allocation-history`, `/not-funded`, `/weights`, `/daily-game-plan` have no caller. From now on rows carry the money mode and base. | OPEN, small (O30) |
| DA-P2 | idle by design | Every portfolio answer is `empty` because no strategy is ACTIVE. | NOTED |
| DA-P3 | transient | The drawdown scheduler could not reach agent-api for equity right after a deploy (connection refused at 03:30), then recovered. | NOTED |
| DA-P4 | important data not stored | No account equity or cash time series exists anywhere (only the day-start figure in `breaker_day_equity.json` and the single current drawdown). For a 20-dollar account the daily value, cash, committed money and money mode over time are what drawdown, live-versus-simulated comparison and any later review need. | QUESTION: build a daily/per-cycle `equity_snapshots` table in live, tagged paper/real? Recommended (O30) |

## live (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-L1 | records do not join | A trade leaves records in four places: the book (pnl), the order log (slippage), the live-decision journal, and the agent's trade audit log (real fills). They share no trade id and not all carry the money mode. `/journal` shows 0 although the book has a closed trade; `/tca/slippage` shows 0 while `/executions` shows a 6.5 bps slippage. | QUESTION: one trade ledger (order -> fill -> position -> close -> pnl, tagged paper/real, strategy and plan ids)? Recommended, fits the allocator's need for real win/loss statistics (O31) |
| DA-L2 | real exit price lost | A position closed outside the scheduler is cut by the book sync at its entry price, pnl 0.0, although the exit fill exists in the agent's audit log. The drill's real round trip is recorded as zero profit and counts as neither win nor loss in the allocator's statistics. | OPEN: let the sync read the exit price from the broker's order history or the audit log (O31) |
| DA-L3 | idle | The live-decision loop evaluates 26 (ticker, YAML strategy) pairs daily, all idle, 0 decisions; research strategies are not part of it. | NOTED, follows from P53 |
| DA-L4 | no outside reader | `/live/executions`, `/lockouts`, `/journal`, `/tca/slippage`, `/status` have no caller outside live. | OPEN, small: agent tools for the ledger views (O31) |
| DA-L5 | legacy figure | `breaker_day_equity.json` still holds the 96,613-dollar day-start equity, unused when a real-money base is set. | OPEN, small (O31) |

## agent (2026-10-08)

| ID | Kind | Finding | Status |
|---|---|---|---|
| DA-A1 | dead feature | `SyncService` (agent memory of research, prices, news, simulator) is never called by production code; `unified_memory.db` is empty and the `query_memory` tool searches nothing. | QUESTION: wire it to the planner cycle, or remove the feature? (O32) |
| DA-A2 | cause lost | 63 of 112 team runs (56%) failed with verdict '' and result '{}'; the cause (upstream model 502, timeouts, connection errors: 48 failed calls) is only in `llm_calls`. Links to O16/O19 (the model server freezing). | OPEN: store the cause on the run (O32) |
| DA-A3 | unbounded | `llm_calls.db` is 183 MB after two days (about 90 MB a day, full prompts and responses), read only by the agent. | OPEN: retention (O32) |
| DA-A4 | noise | 98% of `trade_audit.log` (1,264 of 1,289 lines) is the claim fact-checker's `AuditVerdictFail`; the order records are the other 19 lines. | OPEN: separate file or filter for the fact-checker (O32) |
| DA-A5 | unused duplicate | `telemetry.db` (agent) has empty `llm_calls` and `steps` tables beside the real `llm_calls.db`. | OPEN, small (O32) |
| DA-A6 | tag defect | Every audit entry said `paper_trading: false` on a paper stack and none carried the money mode. | FIXED: problem-log P65, guard `vinu-agent/tests/test_audit_log_money_mode.py` |

## Chains (problems that span components; to be fixed together after the audit)

| Chain | Path | What goes wrong | Fix points |
|---|---|---|---|
| C1 | stock-price speed -> news reaction -> initial-analysis fetch -> saved placeholder -> strategy/research read | A slow candle read (about 3 s per symbol) makes the news bulk read take minutes and sometimes fail; the failed fetch is saved as a completed empty result that replaces the good one; the strategy and research context then see "no news effect". 12% of the news-price results are affected. | (a) news: return articles without price reaction unless asked; (b) initial-analysis: a run whose news fetch failed is an error, not a completed run; never replace a richer result with a placeholder; (c) stock-price: batch candle speed (also DA-R1) |
| C2 | research default -> simulator -> validation -> promotion -> live | Validation counts short profits; live is long-only. | research and simulator defaults `allow_short=false`, settings guard, re-run candidates |
| C3 | ranker partial result -> planner/churn | A ranking of 20 of 50 symbols is saved as the latest (DA-R1). | screener: mark/refuse partial; also fixed by C1(c) |
| C4 | agent sweep calls -> research recipe list | 59% of sweep points fail on names the registry does not know (DA-X4). | one shared recipe list |

