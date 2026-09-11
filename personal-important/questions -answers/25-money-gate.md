# Money Gate - Real Money Gaps + Proofs + Ladder + Kills (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `25`. Related: `13`, `15`, `16`, `19`.
Status: Real money step closed with 6 gaps + 2 top = 8 total. 5 proofs + ladder + kills ready to enforce. Code steps ready to build next, no code changed yet in this doc.

Rating today: money-ready 2/10. Architecture 8/10. Edge proof 0/10. Cannot earn yet. Correct to not fund. After gate green + live 60d: 7-8/10 good. Docs do not make money. Validated forward edge makes money.

---

## 6 gaps with real money (inefficiencies)

### 1. Edge unproven, selection bias
Backtest Sharpe -1.06 STOP today. Even PASS 1.2 can be 1 lucky of 3. Single voice self-verdict, no adversary. Live dies on noise.
Needs: deflated 0.95 + holdout 20 percent + PBO below 0.5 + walk 3 + stress 2020 and 2022 + 30+ trades. Files `backtest_runner/prompt.md:53`, `comparison.py:19`, `pbo.py`.
Money rule: no live without 5 proofs green. Paper only until then.
Status: Open. Build 1 prompt + top 3 unlocks first.

### 2. Costs optimistic gross vs net
Sim 0.001 + slippage 0.0005 fixed. Live spread + queue + latency + partial + borrow + fees 0.2 to 0.5 percent per turn. 100 turns x 0.3 = 30 percent drag. Gross 1.0 becomes net 0.2.
Files `costs.py:73`, `execution.py:33`, `16` gaps 1/3/4/9.
Money rule: rehearsal + paper net-of-cost only. Gross ignored. Slippage loop monthly updates sim. Borrow rate per hard-to-borrow added.
Status: Open. `16` step 1-2 first.

### 3. Sizing overbet on noisy edge
Kelly full on Sharpe SE 0.34 leverages noise. Web ratio edge/noise 1.75 mid-zone, half-Kelly = parity. Full maxDD 41 vs parity 18. Our quarter-Kelly safe default good, but no dynamic vol + no CVaR + no DD halve.
Files `position_sizing.py:15`, `decisions/05-sizing-decision.md:7`, `13` tail vol steps.
Money rule: quarter-Kelly cap 1x + vol targeting `position = target / current` + CVaR 95 gate + DD halve. No full Kelly live.
Status: Open. `13` Now 1-2 first.

### 4. Correlation + concentration live batch
9 per ticker same shape crossover pairwise 0.9 + ACTIVE same = 4x risk. Paper tests single, live holds batch. No gross cap tick.
Files `correlation_gate.py:34`, `service.py:347` composition, `19` sleeves.
Money rule: corr 0.85 gate + symbol 20 percent cap + sleeves 1D/1H separate + turnover cap. Violation skips rank takes next diverse.
Status: Open. `09` diversity + `19` steps.

### 5. Execution + operational live
HALT blocks exits, no time-stop loser sits, no cooldown revenge 2 losses, no idempotency double fill, data lag 30min stale, restart wipes paper before fix, secrets plain leak. Each costs real once.
Files `orchestrator.py:486`, `order_guard.py:31`, `kill_switch.py`, `18` lag alerts, `22` secrets retry.
Money rule: HALT entries-only allow exits, time-stop 30d, cooldown 2 losses lock 24h, idempotency key artifact+cycle+slice, lag 3x alert pause entries, secrets files only.
Status: Open. `15` 1-2 + `16` 1-2 + `18` 8-9 first.

### 6. No money ladder + kill rules
Binary paper vs ACTIVE full size. No ladder paper -> small -> scale. No daily loss halve, portfolio DD flat, pair lock.
Money rule ladder + kills below. No full size day 1. Without ladder first drawdown full size.
Status: Open. This file enforces. See proofs + ladder + kills sections.

---

## 2 more on top (added so nothing missed)

### 7. Broker + vendor outage fallback
Alpaca down, Polygon lag, LLM 400 fail, portfolio unreachable funding skipped fail-closed. Stuck flat cannot exit on outage.
Fix: health banner `17` + auto-pause entries allow exits `15` HALT + second broker env knob Later not now. Read-only UI shows outage + paused. Retry same pattern `22` step 2.
Knobs: `VINU_OUTAGE_PAUSE_ENTRIES=true`, `VINU_BROKER_FALLBACK_URL=` (empty now, Later).
Status: Open. Small docs + knob. Include now.

### 8. Tax + dividends + splits + borrow drag net
Shorts pay borrow daily, shorts owe dividends, splits adjust qty price overnight, taxes short-term vs long-term cut net 20-30 percent. Sim no borrow, no dividend owe, no tax haircut. Paper gross overstates kept.
Fix: borrow rate per hard-to-borrow + dividend calendar check + split adjust before entry `16` step 9 + net-after-tax view 0.7x gross short-term. Paper Sharpe gross + net columns.
Knobs: `VINU_EXEC_BORROW_RATE`, `VINU_EXEC_CORP_ACTION_CHECK` kept `16`, `VINU_NET_TAX_HAIRCUT_SHORT=0.7`, `VINU_NET_TAX_HAIRCUT_LONG=0.85`.
Status: Open. Small params + view. Include now.

HFT latency arms + quantum + options Greeks out of scope equity swing, correctly skipped. Not gaps.

---

## 5 proofs to fund (all must green, no hope funding)

1. Deflated Sharpe 0.95 or more on 30+ trades. File `comparison.py:19`. Corrects trials.
2. Holdout 20 percent pass + gap 5d. Never tuned on holdout. Degrade 0.5 or less.
3. PBO below 0.5 + walk stable pass. Files `pbo.py`, `sweep_grid.py`. Null = FAIL, need 2+ succeeds.
4. Paper 10d for 1D, 5d for 1H, Sharpe over 0 net, degradation 0.5 or less. Files `shadow_evaluator.py:97`. Paper all 9 per ticker, best forward not best backtest.
5. Costs honest net + CVaR gate + lookahead pass + freeze hash. Files `costs.py`, `test_custom_sim.py`, `freeze.py`. Gross ignored.

Any 1 red = no live. Paper continues. Rank2 backup gets chance. No manual override except `VINU_MONEY_GATE_OVERRIDE=false` default.

---

## Size ladder paper 0% -> 10% 30d -> 50% 60d -> 100% (never full day 1)

- Stage 0 paper 0%: 9 BENCHING paper all, 0 ACTIVE. Until 5 proofs green.
- Stage 1 live 10% 30d: 1-2 ACTIVE small. Max position 5 percent, daily loss 2 percent halve, pair lock on. Calibration collects. Lessons start.
- Stage 2 live 50% 60d: scale on DD held + calibration rated 5+ + lessons regime matched. Max position 15 percent. Turbulence gate on.
- Stage 3 live 100%: full mandate 25 percent + budget 100000. Only after live 60d + DD under 15% + lessons compounding. HRP BL auto guard `13` 4-guard green required.
- Downshift auto: portfolio DD 10% halve all, 15% flat cash. Daily loss 5% halt entries allow exits. Pair 2 losses lock 24h. No upshift same week as downshift.

---

## Kills: daily + portfolio + pair + outage (fail-safe, allow exits)

- Daily loss 5% halt entries allow exits. File `breaker/limits.py:9`. Reopen next day flat if paper confirms. Never block invalidation exit.
- Portfolio DD 10% halve all, 15% flat cash. File `19` step 3. Manual re-arm required, no auto resume same day.
- Pair 2 closed losses lock symbol 24h entries, exits allowed. File `15` step 5 cooldown. Prevents revenge.
- Outage health red pause entries allow exits. File `17` banner + `15` HALT. Second broker Later.
- Kill scope symbol vs global pinned. `order_guard.py` + `kill_switch.py` entries vs exits split `15` step 1 + `16` step 2. Risk-reducing always allowed.

---

## Knobs full list for money gate (add to 10 later build)

- Proofs: `VINU_MONEY_GATE_DEFLATED_MIN=0.95`, `VINU_MONEY_GATE_HOLDOUT_REQUIRED=true`, `VINU_MONEY_GATE_PBO_MAX=0.5`, `VINU_MONEY_GATE_MIN_TRADES=30`, `VINU_MONEY_GATE_PAPER_DAYS_1D=10`, `VINU_MONEY_GATE_PAPER_DAYS_1H=5`, `VINU_MONEY_GATE_DEGRADATION_MAX=0.5`.
- Costs net: `VINU_MONEY_GATE_NET_REQUIRED=true`, `VINU_NET_TAX_HAIRCUT_SHORT`, slippage borrow corp flags kept `16`.
- Ladder: `VINU_MONEY_STAGE=paper` (paper, live10, live50, live100), `VINU_MONEY_STAGE_AUTO=true`, `VINU_PORTFOLIO_DD_HALVE_PCT`, `VINU_PORTFOLIO_DD_FLAT_PCT` kept `19`.
- Kills: `VINU_LIVE_MAX_DAILY_LOSS_PCT`, `VINU_LIVE_HALT_POLICY`, `VINU_LIVE_COOLDOWN_AFTER_LOSS`, `VINU_LIVE_PAIR_LOCK_HOURS` kept `15`, `VINU_OUTAGE_PAUSE_ENTRIES`, `VINU_MONEY_GATE_OVERRIDE=false`.
- Future timeframe: same `VINU_SWEEP_INTERVALS` drives gate per interval, no extra knob. 15min gate same thresholds + fills honest required.

---

## Order to enforce (gate doc first build 1 edge second)

1. Gate doc + knobs + ladder + kills wiring read-only. No live change. Do first. This file.
2. Build 1 prompt mature + top 3 writer 9 unlocks PASS. Then 2 fast + view. Then 3 lesson + paper 9. Edge proof 0 to 5 proofs.
3. Costs honest + tail vol + HALT exits + cooldown before Stage 1 live 10%. Safety before money.
4. Stage ladder auto 0 -> 10 -> 50 -> 100 on proofs + DD held + calibration rated. No manual jump.
5. Test: red proof blocks live, ladder upshifts only on green, kills halve flat lock pause allow exits, outage pauses entries, net view shows gross vs kept.

After 1-5, money gate enforced. 2/10 today -> 5/10 paper green -> 7/10 live 60d. Fund only on proof not hope.

---

## All covered proof (nothing missed for real money)

- Edge `backtest_runner/prompt.md:53`, `comparison.py:19`, `pbo.py`, `sweep_grid.py` covered gap 1 + 5 proofs.
- Costs `costs.py:73`, `execution.py:33`, `16` 9 steps covered gap 2 + net rule.
- Sizing `position_sizing.py:15`, `05-sizing` Kelly parity, `13` tail vol covered gap 3.
- Corr `correlation_gate.py:34`, `service.py:347`, `19` sleeves regimes covered gap 4.
- Exec `orchestrator.py:486`, `order_guard.py:31`, `kill_switch.py`, `18` lag, `22` secrets retry covered gap 5.
- Ladder kills here sections covered gap 6.
- Outage health banner `17` + HALT `15` covered top 7. Tax borrow corp `16` step 9 covered top 8.
- Web ML4Trading Kelly parity hybrid, wraquant regime, tradecraft Kelly CVaR, cpz-quant tail robust, risk parity vs Kelly when-wins hybrid kept.
- Repos mapped: Freqtrade dry-run protections 12/15/16, Qlib purge ensemble PIT 08/18/19, VectorBT fast plots 08/17, Nautilus fills catalog parity 12/16/18, Lean cycle admin 15/17, PyPortfolioOpt HRP BL 13/19, FinRL turbulence bake-off 12/20, TradeMaster PRIDE 20, Hummingbot skew 16. No new repo needed.
- 07 sweep 7, 08 1+2+5, 09 top3 9, 10 knobs, 11 paper 9, 12 seven-day 10, 13 risk retention 90d, 14 storage 3x, 15 monitor 7, 16 broker 9, 17 UI 7, 18 data 9, 19 portfolio 11, 20 learning 7 + impact vector, 21 workers, 22 infra, 23 runbooks, 24 corners section 1 + outlines kept. 25 closes money gate. Full docs 01 to 25 closed.
