# Top 3 Per Timeframe - Full Closed Plan (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `09`. Related: `07-sweep-grid-7-inefficiencies.md`, `08-advanced-sweep-adopt.md`.
Status: This step 100% closed after this file. Nothing left out.

---

## What we get in the end (one or multiple?)

Today only one winner goes forward. Sweep makes ranked table of 3, but only top 1 goes to risk, only 1 becomes BENCHING. Others stay in log.
File `vinu-agent/vinu_agent/agent/research_artifact_writer.py:43` writes 1 artifact.
File `vinu-research/comparison.py:19` ranks by deflated Sharpe, best first.

New rule: keep top 3 per timeframe, different shapes, with regime tag. Winner funded, 2 backups stay BENCHING for regime change.

---

## Best: top 3 per 1D + 1H + 15min (9 per ticker)

- 1D top 3: rank1, rank2, rank3. Different shapes. Example: rank1 crossover, rank2 rsi, rank3 bollinger or MACD+rsi mix.
- 1H top 3: same. Rank1, rank2, rank3. Different shapes.
- 15min top 3: same. Rank1, rank2, rank3. Different shapes. Session + day-vol + near-live context. Stored always, traded now per 3-format rule.
- Total 9 per ticker. 27 for AAPL, MSFT, NVDA. Easy to read. You asked 9, correct.
- Tag each: `ticker-timeframe-regime-rank-shape`. Example: `AAPL-1D-trend-rank1-crossover`, `AAPL-1D-range-rank1-rsi`, `AAPL-1H-trend-rank1-bollinger`, `AAPL-15min-trend-rank1-crossover`.
- 1min, 5min, 4H later after 1D+1H+15min green. Not now. Keeps cost low.
- Notebook view: one table per timeframe. Sharpe vs drawdown vs rank. See crowding at once.

Why good: 1D winner and 1H winner differ. Trend winner and range winner differ. One winner hides regime. Top 3 shows how timeframe works.

What mature repos do:
- Freqtrade stores all hyperopt epochs ranked, not winner only. Losers help next round.
- Qlib ensemble mixes top 3, not winner-takes-all. More stable.
- VectorBT shows matrix fast x slow x symbol. See full distribution, not best cell.
- Lean stores ranked signals per resolution daily, hourly, minute separately. Same as per timeframe top 3.

---

## My 3 extra on top (included now)

### 1. Regime-wise tag (include now, small)

What: Add regime column on each of the 9. Trend, range, high-vol.
Where: `vinu-simulator/vinu_simulator/engine/regime.py` + shock_personality angle score.
Why: Crossover wins in trend, loses in range. Without tag, you fund wrong winner.
Cost: Small. 1 column `regime` on artifact + summary.
Rule: Rank per regime too. `1D-trend-top1`, `1D-range-top1` separately.

### 2. Diversity rule (include now, small)

What: Top 3 must be different shapes. Not 3 crossover variants fast 5, 10, 20.
Where: `vinu-research/comparison.py:19` after rank, add filter. Keep best per shape, drop same-shape duplicates.
Why: 1 regime change kills all 3 if same shape. Different shapes survive.
Cost: Small. 1 filter after rank.
Rule: rank1 crossover, rank2 rsi or bollinger, rank3 MACD+rsi mix or zscore. Never 3 same.

### 3. 7-day rehearsal + cost-aware rank (after 1+2 green, medium)

What: Before BENCHING, run 7-day fresh window net-of-cost on top 3. Rank subtracts cost + turnover, not only complexity.
Where: `04-implementation-slices.md:9` Slice A1 Row1. Winner -> 7-day rehearsal via `simulator.py:32` WeightSimulator. Rank in `comparison.py:34` add cost term.
Why: Stops paper winner that wins gross but loses net. Honest BENCHING.
Cost: Medium. 1 extra sim call per top 3.
Rule: Gross Sharpe - cost > 0 and rehearsal Sharpe > 0, else drop from top 3.

---

## Final 3 to close fully (nothing left out after this)

### A. Freeze hash (small, include in 09)

What: Each of the 6 links to data hash. Hash of `data/news:stock-price:features` inputs + window `2022-01-01_2026-07-01`.
Where: `vinu-infra/freeze.py` + `vinu-initial-analysis/RunLog` + artifact field `data_hash`.
Why: Without hash, you cannot prove top 3 came from same data after restart or re-run.
Rule: No hash = no BENCHING. 1 line check.

### B. Correlation gate (small, include in 09)

What: Top 3 must not correlate to existing ACTIVE above 0.85. Check before BENCHING.
Where: `vinu-research/gates/correlation_gate.py:34` with `from_date, to_date, interval`.
Why: 3 new + 1 live same shape = 4x risk. Diversify.
Rule: Correlation >= 0.85 to ACTIVE = skip that rank, take next diverse rank.

### C. Decay + revalidation (small rule, include in 09)

What: Winner decays, backup promotes. Re-check Sharpe every 30 days. Auto promote rank2 if rank1 drops 0.5.
Where: `vinu-research/scheduled/executor.py:148` revalidation scan + regime-recompute scan.
Why: Without this, rank2 sits forever. Market changes, winner dies.
Rule: Rank1 Sharpe drops 0.5 or 30 days pass -> re-run 7-day rehearsal on top 3 -> promote best now.

---

## Timeframes check (repeated for easy read, same as 07)

- 1min 28, 5min 28, 15min 28, 1H 28, 4H 28, 1D 27/27, 1W/1M/6M 1 each.
- Total 170 per ticker. 510 for 3 tickers.
- Sweep today only 1d. New: sweep 1d top 3 + 1H top 3 + 15min top 3 = 9 kept per ticker. 27 for 3 tickers. Paper all 9, 1-2 funded rest backup.

---

## Order to build (one by one, closed list, no left-out)

1. Vectorbt fast wire. `sweep_grid.py:86`. 20 points 10s.
2. Hyperopt Bayesian + pairlist filter. `sweep.py`. 8 smart points.
3. Purge + embargo + triple-barrier. `pbo.py`. Honest PBO.
4. Lookahead guard test. `test_custom_sim.py`. No future leak.
5. Top 3 per 1D+1H+15min with regime tag + diversity rule. `comparison.py:19` + `research_artifact_writer.py:43` (write 9 per ticker, not 1) + notebook view per timeframe.
6. Freeze hash + correlation gate. `freeze.py` + `correlation_gate.py:34`.
7. 7-day rehearsal + cost-aware rank. Slice A1 Row1.
8. Decay revalidation 30 days. `scheduled/executor.py:148`.
9. Ensemble top 3 mix. `comparison.py:33`. After 1-8 green.

After 1-9, sweep filter rank step is done. Next step is downstream risk, capital, shadow. Different step.

---
Link: Paper all 9 + live + stores + paper-days knob is in `11-paper-all-6-live.md`. 09 + 10 + 11 together = sweep to live closed. Paper all 9 rule: store 9 BENCHING, paper all 9, promote best forward paper.

---

## All covered proof (so you see nothing left)

- 07 has 7 inefficiencies. Done.
- 08 has 1+2 + 5 related. Done.
- 09 has top 3 + 3 extra + final 3 close. Done.
- Catalog `02-adoptable-logic-catalog.md:17-26` all mapped: 17 purge done in 08C, 18 ensemble done step 9, 19 hyperopt done step 2, 22 ranking done step 5, 23 turbulence later downstream, 24 dry-run later shadow, 25 PRIDE later risk, 26 LOB later intraday only.
- Ledger `inefficiencies-A-J.md:E` vectorbt open -> step 1. B, D, F, G, H, J already built.
- Slices `04-implementation-slices.md:9` A1 rehearsal -> step 7.

Nothing else present for this step.
