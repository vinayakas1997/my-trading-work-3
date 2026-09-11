# Paper All 6 + Live + Stores + Paper-Days Knob (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `11`. Related: `09-top3-per-timeframe.md`, `10-env-knobs.md`.
Status: Closes paper + live + memory step. Nothing left out for this step.

---

## What is rank 3 basically?

Rank 3 is third best idea in one sweep round.

Example, AAPL 1D sweep 3 points:
- Rank 1: `crossover fast 5 slow 30`, Sharpe 0.8, score 90. Best.
- Rank 2: `rsi period 14 oversold 30`, Sharpe 0.6, score 80. Second.
- Rank 3: `bollinger period 20 dev 2`, Sharpe 0.4, score 70. Third.

All 3 tested on same past candles. Ranked by deflated Sharpe score, not raw Sharpe.
File `vinu-research/comparison.py:19`. Score minus complexity, plus win rate, minus drawdown.

Rank 3 means backup, not funded first. Different shape from rank 1 and 2 by diversity rule.
Useful when market changes. Rank 1 wins in trend, rank 3 wins in range. When rank 1 decays, rank 3 promotes. No re-sweep needed.
Today rank 3 is in log only, lost. After top 3 fix, rank 3 stays BENCHING with tag `AAPL-1D-rank3-bollinger`.

---

## Paper all 6 per ticker - yes, inefficiency if only 1

Today only 1 of 6 goes to paper, because only winner becomes BENCHING.
File `vinu-agent/vinu_agent/agent/research_artifact_writer.py:43` writes 1.
Shadow checks all BENCHING, file `vinu-live/vinu_live/shadow_evaluator.py:44` `evaluate_all`, but only 1 exists to check. So 5 never paper proved.

Paper is no real money. Must paper all 6 per ticker. Then pick best forward paper Sharpe, not best backtest Sharpe.

New rule (inefficiency fix, open):
- Store top 3 per 1D + top 3 per 1H = 6 as BENCHING per ticker. 18 for 3 tickers.
- Shadow papers all 6. `evaluate_all` already loops all BENCHING, no code change needed there, only need 6 to exist.
- Promote best forward paper, not best backtest. Rule: `paper_sharpe > 0` and `degradation <= 0.5`. File `shadow_evaluator.py:97`.
- Cost: paper compute only, no real money risk. More paper rows in `paper_performance.db`, still tiny.
- Status: Open. Needs writer change 1 to 6 + paper-days knob below.

---

## 1) Live thinking good? What other repos do?

Yes. Our live thinking is good. No change needed here.

Our way: 6 BENCHING -> paper 5 to 10 days -> 1 to 2 ACTIVE -> monitor hold or exit.
Promote only if paper Sharpe > 0 and degradation <= 0.5. File `shadow_evaluator.py:97`. Safe, not direct live.

Other repos when they get full optimised strategy:
- Freqtrade: dry-run wallet first, tick fills, then live with edge table. Same paper gate.
- Nautilus + Lean: pre-trade risk gateway + throttle 10 per sec, then live deploy. Same risk gate.
- Qlib: paper ensemble + attribution, then live. Same staged promote.
So our staged way matches mature repos. Good.

---

## 2) Comprehensive analysis stored for next analysis? Yes, 7 places

1. `strategy_store.db` artifacts: code + Sharpe + drawdown + origin_angles + data_hash. Winner only today, 6 after fix.
2. `team_runs`: full LLM trace, idea + sweep ranked table + risk reasoning. Losers stay here only today.
3. `TickerLedger`: stage events `candidate_proposed`, close-out rows with `ref_id`. Next planner reads for K-cap.
4. `trade_plan_book.db`: plans, hold, exit, rebalance. File `trade_plan/orchestrator.py:64`.
5. Calibration outcomes: per artifact accuracy. File `feedback_loop.py:121`. Next screener weights trust.
6. `pnl_attribution` angle: per symbol PnL push. File `feedback_loop.py:135`.
7. `HypothesisRegistry`: thesis + evidence + invalidation reason. Next theory_reviewer reads this.
8. `paper_performance.db`: daily returns per artifact. Survives restart. SQLite persistent.

Gap for next analysis: losers rank2 rank3 not stored as artifacts, only in team_runs log. Next planner cannot see them easily.
Fix: store all 6 as BENCHING. Then next analysis reads all. Plus one `full_progress.db` view planned in `04` file.

So yes stored, but need top 3 store to make next analysis full. After that, next analysis is complete.

---

## 3) Paper-days knob: 5 to 10 controllable

Today hard `min_paper_days 5`. File `vinu-live/vinu_live/shadow_evaluator.py:28`.
Rehearsal 7 days already knob `VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS`. Keep.

New knobs (add to `10-env-knobs.md` + `.env-example` live section in build):
- `VINU_SHADOW_MIN_PAPER_DAYS=5`: change to `10` any time + restart. No rebuild.
- Better per interval: `VINU_SHADOW_MIN_PAPER_DAYS_1D=10`, `VINU_SHADOW_MIN_PAPER_DAYS_1H=5`. 1D needs longer proof, 1H faster.
- Wire into `ShadowEvaluator.__init__` via config, same pattern as research `load_config`.

Tradeoff: 5 days fast to live, noisy. 10 days safe, slow. Suggest 10 for 1D, 5 for 1H. Best balance.

Order: add knob first (1 file example + 1 config), then paper all 6, then promote best forward paper.

---

## Counts after implemented (same as 09, repeated for easy read)

- Per ticker: 1D top 3 + 1H top 3 = 6 BENCHING. Each papered. 1 to 2 ACTIVE. Rest backup.
- 3 tickers: 18 BENCHING. 3 to 6 ACTIVE max by budget 100000.
- Add 15min later via `VINU_SWEEP_INTERVALS`: 9 per ticker. 27 for 3 tickers. Same paper all rule.
- Each result has: ticker-timeframe-regime-rank-shape, Sharpe, drawdown, win rate, trade count, completeness, PBO, walk_forward, data_hash, run_id, paper Sharpe, degradation.

---

## Order to build (closed, no left-out)

1. Writer 1 to 6. `research_artifact_writer.py:43`. Store top 3 per interval, not winner only.
2. Paper-days knob. `shadow_evaluator.py:28` + `.env-example` + config. 10 for 1D, 5 for 1H.
3. Paper all 6. No new code, `evaluate_all` already loops. Verify 6 paper rows.
4. Promote best forward paper. Keep rule `paper_sharpe > 0` + `degradation <= 0.5`.
5. Next analysis reads all 6. Planner + theory_reviewer + calibration trust. Plus `full_progress.db` view.

After 1-5, paper + live + memory step done.

---
Link: 7-day finish 10 points closed is in `12-seven-day-finish-10.md`. 09 + 10 + 11 + 12 together = sweep to live to feedback closed.
