# Simulation Storage - What Stored + Rehearsal Full 3x (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `14`. Related: `09`, `10`, `11`, `12`, `13`.
Status: Store-full plan saved. Code steps 1-4 ready to build next, no code changed yet in this doc.

---

## 1. What simulation stores today (per run_id)

Folder `simulations/ab/run_id/` in `data/simulator`. File `vinu-simulator/storage/results.py:45`.

- `equity.parquet`: date, portfolio_value, daily_return. File `results.py:48`. Equity curve + daily PnL series. From this Sharpe, drawdown curve, turnover.
- `trades.parquet`: date, symbol, side, shares, price, cost, weight_before, weight_after. File `results.py:62`. Every executed trade. From this win rate, profit factor, avg win and loss, trade count.
- `weights.parquet`: date + weights history. Position path over time.
- `meta.json`: strategy_name, run_id, timestamp. File `results.py:79`. Link back to research sweep.

What else stored with it, same run_id linked:

- Metrics bundle 30+ numbers. File `vinu-simulator/models/metrics.py:8`. Total return, CAGR, vol, Sharpe, Sortino, maxDD, Calmar, win rate, skew, kurt, VaR 95 and 99, CVaR 95, tail ratio, DD duration, avg DD, recovery days, profit factor, avg win pct, avg loss pct, turnover, Sharpe SE, p-value, CI 95 low and high, beta, alpha, tracking error, IR, correlation, up and down capture.
- Validation block. File `engine/validation.py:9`. Monte Carlo p-value, block bootstrap, price-path resample, walk-forward windows, BCa CI, verdict passed true or false + reasons. Always computed, 0.7s extra. Same call, no separate call.
- Sweep rank + PBO. File `vinu-research/sweep_grid.py:86`. Ranked table best first by deflated Sharpe, completeness fraction, PBO overfit, walk_forward stable. Stored in `team_runs` + research trace, linked by run_id, not in sim folder.

So per backtest full evidence: curve + trades + weights + 30 metrics + validation + rank. Not only Sharpe.

---

## 2. What rehearsal stores today (small, gap)

File `vinu-research/models.py:625` `PaperRehearsalResult`. Bar-by-bar trailing 7 calendar days, about 5 trading days. File `vinu-research/loop.py:835`. Same simulator + T+1 + cost, so comparable.

Today only summary:
- `rehearsal_from`, `rehearsal_to`, `in_sample_sharpe`, `rehearsal_sharpe`, `rehearsal_max_drawdown`, `rehearsal_total_return`, `rehearsal_trade_count`, `passed true or false`, `note`, `raw_metrics dict`.
- No `rehearsal_run_id`. Link dropped. Cannot load equity.
- No equity curve. No trades list. No weights. No regime. No conditions. No overlap score.

Gap: cannot study deeper. Are trades similar backtest vs rehearsal? Unknown. What conditions encountered? Unknown. Real vs paper divergence where? Unknown.

---

## 3. Full store plan (3x per sweep, tiny, worth it)

Store full = 3 stages per strategy: backtest + rehearsal + paper. Same shape. Tiny parquet, few KB per run. Worth it. You said yes.

Extend `PaperRehearsalResult` with 4 new fields, no new service:

1. `rehearsal_run_id str`: link to `simulations/ab/run_id/` equity + trades + weights. No new storage, just keep id from `loop.py:867` rehearsal backtest call. Today dropped, must keep.
2. `regime_breakdown dict`: bull, bear, sideways, high_vol Sharpe + count + return on rehearsal window. Call `regime.py:33` `per_regime_performance`. Same as sim side. Tells which regime rehearsal saw.
3. `conditions dict`: vol 21d rolling, VIX turbulence, costs paid, slippage paid, turnover. From sim metrics + `costs.py` + `vinu-tools` VIX. Tells what market felt like.
4. `trade_overlap float`: percent same symbols, dates, sides backtest vs rehearsal. Via `attribution.py:10` match. Tells if behavior same or drifted. 0.2s extra.

Store per top 3, not winner only. 6 per ticker (1D top 3 + 1H top 3) x 3 stages = 18 stores per ticker. 54 for 3 tickers. Still KBs. Small writes, big study.

Paper same shape: `paper_performance.db` daily returns already persistent. Add regime + conditions per artifact side table. Shadow `evaluate_all` already loops all BENCHING, no change there, only need 6 to exist. File `shadow_evaluator.py:44`.

Side-by-side notebook view, 1 table 4 columns: backtest vs rehearsal vs paper vs live. Same rows: Sharpe, drawdown, trades, regime breakdown, conditions, overlap. New `notebooks/rehearsal_compare.py`. You see at once where it breaks: tune vs rehearsal vs forward vs live.

---

## 4. Order to build code (1-4, after docs, tests included)

1. Models extend. `vinu-research/models.py:625` add 4 fields above. Old tests pass. New fields default empty, no break.
2. Loop return full. `vinu-research/loop.py:835` keep run_id + compute regime + conditions + overlap before return. Do for top 3 per interval. Verify link loads equity.
3. Paper same shape. `vinu-live/shadow_evaluator.py:44` store regime + conditions per artifact. Keep rule `paper_sharpe > 0` + `degradation <= 0.5`.
4. Notebook + tests. `notebooks/rehearsal_compare.py` 4-column view. Tests `vinu-research/tests/test_paper_rehearsal_full.py` assert run_id + regime + overlap present. `vinu-simulator/tests/test_results_link.py` assert link loads.

Knobs (add to `10` later build, no change now):
- `VINU_REHEARSAL_STORE_FULL=true`: full vs summary rollback.
- `VINU_REHEARSAL_REGIME_ENABLED=true`, `VINU_REHEARSAL_OVERLAP_ENABLED=true`.
- Existing kept: `VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS=7`, `VINU_SHADOW_MIN_PAPER_DAYS` 10 for 1D 5 for 1H.

Tradeoff decided: top 3 full, not winner-only full. 18 vs 3 stores per ticker. Worth it. Overlap 0.2s acceptable.

---

## All covered proof (nothing left for storage step)

- Sim storage `results.py:45,48,62,79` covered equity trades weights meta.
- Metrics `models/metrics.py:8` 30 numbers covered.
- Validation `engine/validation.py:9` covered Monte Carlo + bootstrap + walk-forward.
- Rank `sweep_grid.py:86` + `comparison.py:19` covered ranked + PBO.
- Rehearsal `models.py:625` + `loop.py:835,867,899` covered summary gap + pass rule.
- Regime `regime.py:7,33` covered tag + breakdown.
- Attribution `attribution.py:10` covered overlap match.
- Costs `costs.py:73` + `simulator.py:103` T+1 covered conditions.
- Shadow `shadow_evaluator.py:28,44,92,97,122` covered paper days + promote + insufficient_data.
- Feedback `feedback_loop.py:86` covered close learning.
- 07 to 13 chain kept. 14 closes storage. Next is code 1-4 build.
