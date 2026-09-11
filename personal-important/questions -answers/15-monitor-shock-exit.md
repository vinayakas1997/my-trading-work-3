# Monitor Shock Exit - How It Works + Gaps + Repos Extras (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `15`. Related: `11`, `12`, `13`.
Status: Monitor step closed with 4 gaps + 3 extras. Code steps ready to build next, no code changed yet in this doc.

---

## How monitor works today (4 goods)

1. Cycle every 90s. Reads all ACTIVE trade plans. For each symbol computes live metrics, checks frozen invalidation metric, operator, threshold. File `vinu-live/trade_plan/orchestrator.py:398`, `condition_evaluator.py:38`. Zero LLM, mechanical only. Good.
2. Shock off-cycle trigger. `shock_clustering` + `shock_personality` fire = immediate check, not wait 90s. Debounce 60s per symbol. File `orchestrator.py:107`. Batch top 5 by shock score over 0.5 auto prioritized. File `orchestrator.py:223`. Built G fix. Good.
3. Breaker before every order. Daily loss 5 percent, aggregate VaR, exposure. File `breaker/engine.py:25`, `breaker/limits.py:9`. Reconciles book vs broker every cycle. File `orchestrator.py:658`. Good.
4. Rebalance advisory only. Capital asks, monitor decides. Invalidation first, rebalance second. Gain protect 5 percent holds profitable. File `orchestrator.py:428,430`. Stop update exists for contingency actions. File `orchestrator.py:511`. Live metrics compute. File `live_metrics.py:28`. Good.

---

## 4 gaps in monitor (inefficiencies)

### 1. HALT blocks exit too
File `orchestrator.py:486` `exit_blocked_by_breaker`. Breaker HALT in crash skips invalidation exit. Position stuck falling.
Fix: split `HALT_ENTRIES` vs `HALT_ALL`. Block entries always on HALT. Allow risk-reducing exits on HALT. This is Row 12 kill policy undecided. Small, high safety. Do first.
Knobs: `VINU_LIVE_HALT_POLICY=entries_only`, `VINU_LIVE_MAX_DAILY_LOSS_PCT=0.05`.
Status: Open.

### 2. No time-stop
Triple-barrier has max-hold days in research, but live has no max-hold enforce. Loser sits forever if no invalidation hits.
Fix: add `max_hold_days` rule from plan. Auto exit on expiry with reason `time_stop`. Read from `trade_plan_data`, fallback 30 days knob.
Knobs: `VINU_LIVE_MAX_HOLD_DAYS=30`.
Status: Open. Small. Do first with 1.

### 3. No trailing default when plan missing it
`update_stop_loss` exists File `orchestrator.py:511` but only runs when plan has trailing contingency action. If plan has no trailing rule, stop never moves.
Fix: default trailing 2x ATR when plan missing it. Compute ATR from live bars, update stop each cycle, never move down for long.
Knobs: `VINU_LIVE_TRAILING_ENABLED=true`, `VINU_LIVE_TRAILING_ATR_MULTIPLE=2.0`.
Status: Open. Small. After 1-2 green.

### 4. Static thresholds, no vol scaling
Invalidation `-8 percent` fixed. High vol 2020 crash hits noise. Calm market too loose.
Fix: scale threshold by current vol ratio. `live_threshold = base x (current_ATR / base_ATR)`. Same pattern as risk vol targeting `13` doc.
Knobs: `VINU_LIVE_VOL_SCALING_ENABLED=true`, `VINU_LIVE_VOL_LOOKBACK_DAYS=21`.
Status: Open. Small formula. After 1-2 green.

---

## 3 advanced from other repos on top

### 5. Cooldown + pair lock (Freqtrade protections)
After 2 losses on AAPL, lock AAPL 24h. We have debounce 60s only, no loss lock. Revenge trading possible.
Fix: `cooldown_after_loss` + `max_drawdown_pair_lock`. Count closed losses per symbol in book, lock entries, allow exits. Same shape as Freqtrade `protections` low profit pairs lock + cooldown.
Knobs: `VINU_LIVE_COOLDOWN_AFTER_LOSS=2`, `VINU_LIVE_PAIR_LOCK_HOURS=24`.
Status: Open. Low effort. Good with 3-4 batch.

### 6. Bracket + partial scale-out (Nautilus)
Trailing stop + take-profit bracket attached at entry, partial 50 percent at 1R target. We do full exit or rebalance reduce only.
Fix: on entry store bracket take-profit + stop. At 1R move stop to breakeven + reduce 50 percent via `reduce_position`. Rest runs to invalidation or trailing.
Knobs: `VINU_LIVE_BRACKET_ENABLED=false` (false now, true after 1-4 green), `VINU_LIVE_PARTIAL_PCT=0.5`, `VINU_LIVE_TAKE_PROFIT_R=1.0`.
Status: Open. Medium. Needs bracket store in book.

### 7. Turbulence pause entries, allow exits (FinRL + Hummingbot)
Pause entries when VIX high, allow exits. Our HALT blocks both today. Plus inventory skew sizes down when exposure high.
Fix: VIX turbulence gate before entry only, same feature as `12` step 9. Exits always allowed. Inventory target skews new size down as exposure rises.
Knobs: `VINU_LIVE_TURBULENCE_PAUSE_ENTRIES=true`, `VINU_LIVE_TURBULENCE_VIX_THRESHOLD=30`, `VINU_LIVE_INVENTORY_SKEW_ENABLED=false` (later).
Status: Open. Small gate + later skew.

---

## Knobs full list for monitor (add to 10 later build)

- `VINU_LIVE_CYCLE_INTERVAL_SEC=90`, `VINU_LIVE_SHOCK_DEBOUNCE_SEC=60`, `VINU_LIVE_SHOCK_MAX_BATCH=5`, `VINU_LIVE_SHOCK_SCORE_THRESHOLD=0.5`.
- `VINU_LIVE_HALT_POLICY=entries_only`, `VINU_LIVE_MAX_DAILY_LOSS_PCT=0.05`.
- `VINU_LIVE_MAX_HOLD_DAYS=30`, `VINU_LIVE_TRAILING_ENABLED`, `VINU_LIVE_TRAILING_ATR_MULTIPLE`, `VINU_LIVE_VOL_SCALING_ENABLED`.
- `VINU_LIVE_COOLDOWN_AFTER_LOSS`, `VINU_LIVE_PAIR_LOCK_HOURS`, `VINU_LIVE_BRACKET_ENABLED`, `VINU_LIVE_PARTIAL_PCT`, `VINU_LIVE_TURBULENCE_PAUSE_ENTRIES`.
- Existing kept: `VINU_LIVE_DATA_ROOT`, rebalance queue path, breaker state. No duplicate.

Future add timeframe: same `VINU_SWEEP_INTERVALS` drives monitor symbols, no extra knob. Monitor reads ACTIVE plans whatever interval swept.

---

## Order to build (safety first, closed 7)

1. HALT entries-only + time-stop. 1-2 together. Highest safety. Small.
2. Trailing default + vol scaling + cooldown lock. 3-5 together. Medium small. After 1 green.
3. Bracket partial + turbulence pause. 6-7 together. After 2 green. Needs bracket store + VIX feature.
4. Test: HALT crash test exit allowed entry blocked, time expiry exit, trailing moves up never down, cooldown locks after 2 losses, bracket halves at 1R, turbulence pauses entries allows exits.

After 1-4, monitor done. Next is 2 broker fills + 7 UI status. Different docs.

---
Link: Broker fills 4 gaps + 3 extras + 2 top is in `16-broker-fills.md`. 15 -> 16 = monitor -> broker closed.

---

## All covered proof (nothing missed for monitor)

- Cycle `orchestrator.py:100,263,389`, shock `107,140,223`, debounce `105`, batch prioritized `238`, invalidation `398,480`, rebalance `414,430`, breaker `engine.py:25`, limits `limits.py:9`, reconcile `658`, metrics `live_metrics.py:28`, book `positions.py:298` update_stop_loss, protect `428` 5 percent. All read.
- Gaps mapped: HALT exit Row 12 kill policy, time-stop triple-barrier research, trailing default plan-missing, vol scaling risk `13` pattern.
- Repos mapped: Freqtrade protections cooldown lock, Nautilus bracket partial fills, FinRL turbulence VIX, Hummingbot inventory skew. Qlib purge done 08, Lean consolidators same as cycle. No new repo needed.
- Ledger `inefficiencies-A-J.md:G` auto-wire built `d4c338ea` + `feat-latency FG` kept. F allocator retry kept. H ref_id kept.
- Slices `04:18-19` A2 shock + replace kept. B risk gateway + throttle later broker doc, not here.
- 09 top3, 10 knobs, 11 paper all 6, 12 seven-day 10, 13 risk full, 14 storage full kept. 15 closes monitor.
