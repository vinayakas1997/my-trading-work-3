# 7-Day Finish - 10 Points Full Closed (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `12`. Related: `09`, `10`, `11`.
Status: 7-day rehearsal + shadow + promote + feedback step closed. Nothing left out.

---

## What happens when 7 days finish

Two checks, not live money yet.

Rehearsal 7 calendar days, about 5 trading days, bar by bar, same simulator + cost.
File `vinu-research/loop.py:704`, config `vinu-research/config.py:153`.

When 7 days finish:
- Compute rehearsal Sharpe. Compare to in-sample Sharpe. Degradation = (in_sample - rehearsal) / in_sample.
- If degradation over 0.5, file `loop.py:899`, reject. No BENCHING. Try next idea.
- If pass, write BENCHING. Hand to risk gatekeeper.

Shadow paper 5 days finish, file `vinu-live/vinu_live/shadow_evaluator.py:92`:
- Collect daily returns in `paper_performance.db`. Less than 5 = `insufficient_data`, wait more.
- When 5 to 7 done, compute paper Sharpe. Same 0.5 rule.
- If `paper_sharpe > 0` and `degradation <= 0.5`, promote BENCHING to ACTIVE. File `shadow_evaluator.py:99`. Capital funds 1 to 2 next 90s. Monitor starts.
- If below, `below_threshold`. Stay BENCHING backup. Rank 2 gets chance.

After live close, file `feedback_loop.py:86`: writes calibration, pnl attribution, hypothesis evidence, ticker ledger. Next research reads this.

So 7 days = pass to BENCHING or reject. Paper 5 days = pass to ACTIVE or stay backup.

---

## 4 inefficiencies in 7-day gate

### 1. 7 days calendar, not trading days
File `vinu-research/config.py:153` says 7 calendar ~5 trading. Weekends no bars. Confusing.
Fix: knob trading days 5, not calendar 7. Count bars, not days.
Status: Open. Small.

### 2. Rehearsal overlaps in-sample
File `vinu-research/loop.py:835` trailing window ending at `to_date`. That window already used to tune. Not true out-of-sample. Passes easy.
Fix: exclude tuning range + 5-day gap. Or use holdout after `to_date`.
Status: Open. Small rule.

### 3. 5 paper days Sharpe noisy
File `shadow_evaluator.py:122` needs 5 returns. 5 points std unstable. 1 lucky day = false promote.
Fix: per-interval knob. 10 for 1D, 5 for 1H. See `10-env-knobs.md` knobs 22-23 + `11` file.
Status: Open. Knob planned.

### 4. Degradation math unstable near zero
File `shadow_evaluator.py:92` divides by `abs(backtest_sharpe)`. Backtest 0.1 + small drop = huge degradation.
Fix: also require absolute `paper_sharpe > 0.3`, not only `> 0`.
Status: Open. 1 line.

---

## My 2 suggestions on top

### 5. Partial size, not all-or-none
Today degrade 0.1 same size as degrade 0.4. File `shadow_evaluator.py:97` true or false.
Better: 0.1 full size, 0.3 half size, 0.4 quarter size. Mature FinRL + Nautilus do vol-adjusted sizing.
Fix: scale in capital allocator. Small change.
Status: Open. After 1-4 green.

### 6. Fast auto-pause after ACTIVE
Today live decay waits 30-day revalidation. File `scheduled/executor.py:148`. Too slow.
If live drops 3 days row, auto-pause to BENCHING, not wait 30 days. Add 3-day fast check in monitor.
Fix: 1 rule in orchestrator. Small.
Status: Open. After 1-4 green.

---

## 4 more from other repos on top (you missed, I missed earlier too)

### 7. Fill realism gap (Nautilus)
Source `03-per-repo-deep-dive/nautilus-fills-catalog.md:20`.
Rehearsal has T+1 + cost, but no spread, no queue position, no latency. Live has all 3. Rehearsal optimistic.
Fix: harden `vinu-simulator/engine/costs.py:73` with spread + queue + latency to `simulator.py:103`.
Status: Open. Small code, honest rehearsal.

### 8. Research-live parity test (Nautilus)
Source `nautilus-fills-catalog.md:22`. Research replay and live must same event order, nanosecond tick. Today no parity test.
Fix: 1 replay test same code same bars same fills.
Status: Open. 1 test.

### 9. Turbulence gate at promotion (FinRL)
Source `03-per-repo-deep-dive/finrl-5agent.md:22`. Even if 7-day Sharpe passes, if VIX high, hold promotion. No entry in storm.
Fix: VIX feature in `vinu-tools`, gate in `shadow_evaluator.py:97` before promote.
Status: Open. Small gate, big safety.

### 10. Sizing HRP vs Kelly (PyPortfolioOpt, Row 5)
Source `03-per-repo-deep-dive/pyportfolioopt-HRP.md:21`. Today `fractional_kelly` in `config.py:106`. HRP better with no return estimate, L2 de-concentrates.
Fix: decide Kelly vs HRP vs ATR, document, parameterize. Decision first, code next.
Status: Open. Decision + small code.

---

## Order to build (closed 10, one by one)

1. Trading days knob + overlap gap fix. 1-2 together. Honest gate.
2. Paper-days per interval 10/5 + absolute Sharpe 0.3 bar. 3-4 together.
3. Fill + parity + turbulence gate. 7-9 together. Honest live.
4. Partial size + auto-pause. 5-6 together. Safe sizing.
5. HRP decision. 10 last. Needs 1-4 green first.

After 1-5, 7-day step done. Next is capital + monitor scale. Different step.

---

## All covered proof (nothing left)

- Rehearsal files `loop.py:704,835`, `config.py:153`, `models.py:625` covered 1-2.
- Shadow files `shadow_evaluator.py:28,92,97,122` covered 3-4 + promote rule.
- Feedback `feedback_loop.py:86,121,135` covered learning close.
- Catalog `02:17-26` mapped: 17 purge done 08, 18 ensemble 09 step 9, 19 hyperopt 08, 20 gateway later live, 21 freeze 09, 22 ranking 09, 23 turbulence here 9, 24 dry-run later shadow, 25 PRIDE later risk, 26 LOB later intraday.
- Deep dives mapped: vectorbt 08, qlib PIT 08C, freqtrade leak 08A-B, nautilus here 7-8, finrl here 9, pyportfolioopt here 10.
- Ledger `inefficiencies-A-J.md` E open -> 08 step 1. B D F G H J built. A built dedupe.
- Slices `04:9` A1 rehearsal -> here step 3 in order list above.

Nothing else present for 7-day finish step.

---
Link: Simulation storage what stored + rehearsal full 3x is in `14-simulation-storage.md`. 12 + 14 together = 7-day gate + full evidence closed.
Link: Monitor shock exit 4 gaps + 3 extras is in `15-monitor-shock-exit.md`. 12 -> 15 = finish gate -> live monitor closed.
