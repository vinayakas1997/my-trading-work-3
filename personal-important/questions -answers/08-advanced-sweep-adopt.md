# Advanced Sweep Adopt - Vectorbt + Hyperopt + 5 Related Logics (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `08`. Related: `07-sweep-grid-7-inefficiencies.md`, `03-vectorbt-not-connected.md`.

---

## Your choice: 1+2

1. Vectorbt fast. 20 points in about 10s. Vector parallel. Not one by one loop.
2. Hyperopt Bayesian smart. Try 8 smart points, not 20 brute points. Learns which params are good.

Together: fast + smart. 8 tries in 10s, rank fast, then risk quick.
Same validation kept: `completeness 0.95`, `PBO 0.5 / 0.7`, `walk_forward stable`, deflated Sharpe rank.

Proof files:
- Slow today: `vinu-research/sweep.py:135` POST per param loop.
- Cap: `vinu-research/sweep_grid.py:37` max 20 per round, today uses 3.
- Vectorbt idea: `new-vision/other-our-repo-full-research-features/03-per-repo-deep-dive/vectorbt-sweep.md:20`.
- Hyperopt idea: `new-vision/other-our-repo-full-research-features/02-adoptable-logic-catalog.md:19` Freqtrade optimize.

---

## 5 other awesome logics for same sweep step

### A. Pairlist pre-filter (Freqtrade) - include now, cheap

What: Before sweep, drop illiquid tickers by volume and volatility.
Why: Saves LLM + sim cost. No sweep on bad ticker.
Where: `vinu-agent/scheduler_workers.py` Gate + `vinu-research/sweep.py` before grid.
Source: `03-per-repo-deep-dive/freqtrade-leak-guard.md:22`.
Effort: Low. 1 file. Good to include with 1+2 now.
Status: Open.

### B. Lookahead guard (Freqtrade) - include now, cheap test

What: After sweep winner, scan code if it uses future bar `data[i+1]` to trade `data[i]`. If yes, auto FAIL.
Why: Stops false PASS. Perfect foresight cannot profit in live.
Where: `vinu-simulator/tests/test_custom_sim.py` new test + post-sweep scan on winner `generate_weights`.
Source: `03-per-repo-deep-dive/freqtrade-leak-guard.md:21`.
Effort: Low. 1 test file. Good to include now.
Status: Open.

### C. Purged + embargo CV (Qlib, Lopez de Prado ch.7) - include now, medium

What: Add 5-day gap between train and test in walk-forward. Purge overlapping labels. Add triple-barrier label (take-profit, stop-loss, max-hold).
Why: Our walk-forward has no gap now. Price leaks. PBO looks clean but is not honest.
Where: `vinu-research/pbo.py` + `vinu-research/sweep.py:159` + walk_forward block.
Source: `02-adoptable-logic-catalog.md:17`.
Effort: Medium. Makes PBO honest. Good to include with 1+2 now.
Status: Open.

### D. Ensemble top 3 (Qlib) - after 1+2 green, medium

What: Today take winner only. Better mix top 3 by rank score. Stable than 1 best.
Why: Winner often lucky. Mix of 3 survives regime change better.
Where: `vinu-research/comparison.py:33` rank_candidates + `vinu-portfolio/service.py:build_portfolio`.
Source: `02-adoptable-logic-catalog.md:18`.
Effort: Medium. Do after 1+2 green, not same time. Needs attribution per factor.
Status: Open, next batch.

### E. Signal ranking view (Lean + VectorBT) - include now, low notebook

What: Show distribution of 20 points. See crowding. Tells why always `crossover`.
Why: Debug view. You can see idea crowding. Ranked signal + distribution map.
Where: `vinu-research/sweep_grid.py:86` + new `notebooks/`.
Source: `02-adoptable-logic-catalog.md:22`.
Effort: Low. Notebook only. Good to include now for debug.
Status: Open.

---

## Not for this step, for later (risk and shadow, not sweep)

- Turbulence index + vol-adjusted sizing (FinRL). File `02:23`. For risk sizing in stress. Do after sweep green.
- 8-metric PRIDE star + Monte Carlo stress (TradeMaster). File `02:25`. Broader than Sharpe-only. For risk report.
- Dry-run wallet with fills tick-by-tick (Freqtrade). File `02:24`. For `shadow_evaluator.py:23`. Today Sharpe-only. For shadow step.
- LOB spread + market impact (Qlib). File `02:26`. Only if intraday 1min. Later.

---

## Timeframes check (same as 07, repeated for easy read)

- 1min 28, 5min 28, 15min 28, 1H 28, 4H 28, 1D 27/27, 1W/1M/6M 1 each.
- Total 170 per ticker. 510 for 3 tickers.
- Today sweep only 1d. 1H sweep is next after 1+2.

---

## Order to build (one by one)

1. Vectorbt fast wire. File `sweep_grid.py:86`. Cap 20. 10s for 20 points.
2. Hyperopt Bayesian + pairlist. File `sweep.py`. 8 smart points.
3. Purge + embargo + lookahead guard. Files `pbo.py`, `test_custom_sim.py`. Honest PASS.
4. Ranking notebook. File `notebooks/`. See crowding.
5. Ensemble top 3. File `comparison.py:33`. After 1-4 green.
6. 1H sweep after 1d PASS. Add interval choice.

Next: pick 1 to build. I suggest 1 vectorbt first, then 2 Hyperopt together.

---
Link: Full closed top 3 plan is in `09-top3-per-timeframe.md`. 08 + 09 together = nothing left out for sweep step.
