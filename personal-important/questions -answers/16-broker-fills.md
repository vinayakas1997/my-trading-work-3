# Broker Fills - How It Works + Gaps + Repos Extras + Top 2 (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `16`. Related: `13`, `15`.
Status: Broker step closed with 4 gaps + 3 extras + 2 top = 9 total. Code steps ready to build next, no code changed yet in this doc.

---

## How broker works today (3 goods)

1. Guard before every order. File `vinu-agent/vinu_agent/broker/order_guard.py:31`. Checks mandate + kill switch + active artifact + daily limits SQLite + throttle 10 per sec. Fresh instance per trade, throttle per burst. Good.
2. Execution TWAP 6 slices + VWAP volume profile. File `vinu-live/vinu_live/execution.py:33`. Splits evenly or by volume curve, quantize floor. Good for large orders.
3. Reconcile + breaker + book persist. Book `trade_plan_book.db`, breaker daily 5 percent, reconcile broker vs book every cycle. Same as monitor `15` doc. Good.

---

## 4 gaps in broker (inefficiencies)

### 1. Sim vs live fill mismatch
Sim uses Almgren-Chriss + T+1 + cost 0.001 + slippage 0.0005. Live Alpaca has spread + queue + latency + partial fills. No spread, no queue, no latency in sim. File `vinu-simulator/engine/costs.py:73`.
Result: rehearsal passes, live slips 0.2 to 0.5 percent.
Fix: add spread + queue position + latency to sim, same as `12` step 7. Small. Do first with 2. High honesty.
Knobs: `VINU_SIM_SPREAD_BPS`, `VINU_SIM_QUEUE_PCT`, `VINU_SIM_LATENCY_MS`.
Status: Open.

### 2. Kill policy undecided
Halt blocks entries + exits today. Should block entries, allow exits. Same as monitor gap 1 `15` doc. Files `order_guard.py:16`, `kill_switch.py`, Row 12 decision open.
Fix: split scope global vs symbol, entries vs exits. `HALT_ENTRIES` blocks new, allows close. Small, highest safety. Do first.
Knobs: `VINU_LIVE_HALT_POLICY=entries_only`, `VINU_KILL_SCOPE=symbol`.
Status: Open.

### 3. No slippage feedback to sim
Live pays real slippage, sim keeps 0.0005 fixed. No loop writes live slippage back to `costs.py`.
Fix: monthly job avg live slippage per symbol from `trade_plan_book.db` fills vs sim cost, update sim slippage param. Small job.
Knobs: `VINU_SLIPPAGE_FEEDBACK_ENABLED=true`, `VINU_SLIPPAGE_UPDATE_INTERVAL_DAYS=30`.
Status: Open. After 1-2 green.

### 4. No partial fill handling explicit
Alpaca partial fills. Book expects full or fail. `trades.parquet` has shares + cost, but live partial needs split + retry remainder.
Fix: split + remainder queue, like Nautilus `tests/test_fills.py` partial when volume small. Small.
Knobs: `VINU_EXEC_PARTIAL_ENABLED=true`, `VINU_EXEC_MAX_PCT_OF_VOLUME=0.1`.
Status: Open. After 1-2 green.

---

## 3 advanced from other repos on top

### 5. Nautilus fill, latency, book models
Source `03-per-repo-deep-dive/nautilus-fills-catalog.md:20`. Queue + spread + latency + book depth + deterministic replay.
Adopt queue + spread first, book depth later intraday only. Same as gap 1 fix, plus replay test same code same bars same fills.
Status: Open. Small + 1 test.

### 6. Freqtrade dry-run wallet tick fills
Source `freqtrade-leak-guard.md:23`. Wallet-level tick fills vs our Sharpe-only shadow. Upgrade shadow to wallet diff not just Sharpe.
Where: `shadow_evaluator.py:23` + `simulator/service.py`. Medium, after fills fix. Same as catalog `02:24`.
Status: Open. Later batch.

### 7. Hummingbot TWAP, VWAP + inventory skew executors
We have TWAP and VWAP plan, no inventory skew executor. Add skew sizes down when exposure high.
Where: `execution.py:33` plan_twap + volume profile. Add `inventory_skew` param 0 to 1.
Knobs: `VINU_EXEC_TWAP_SLICES=6`, `VINU_EXEC_INVENTORY_SKEW_ENABLED=false` (false now, true after 1-4 green).
Status: Open. Small param.

---

## 2 more on top (added so nothing missed)

### 8. Idempotency + retry exactly-once
Today throttle + daily SQLite, but no order idempotency key. Retry after timeout can double fill.
Fix: add `client_order_id = artifact + cycle + slice` on every live order, broker de-dupes on retry. Nautilus pattern client id + ack.
Knobs: `VINU_EXEC_IDEMPOTENCY_ENABLED=true`.
Status: Open. Small. Prevents double. Include now.

### 9. Borrow cost + corporate actions
Shorts pay borrow, splits and dividends change price. Sim `allow_short true`, cost 0.001, no borrow rate, no split adjust beyond provider. Live Alpaca charges borrow + handles splits.
Fix: add `borrow_rate` per hard-to-borrow + split and dividend adjust check before entry. Small params.
Knobs: `VINU_EXEC_BORROW_RATE=0.0`, `VINU_EXEC_CORP_ACTION_CHECK=true`.
Status: Open. Small. Include now.

---

## Knobs full list for broker (add to 10 later build)

- Fill: `VINU_SIM_SPREAD_BPS`, `VINU_SIM_QUEUE_PCT`, `VINU_SIM_LATENCY_MS`, `VINU_SIMULATOR_TRANSACTION_COST_PCT` kept, `VINU_SIMULATOR_SLIPPAGE_PCT` kept.
- Kill: `VINU_LIVE_HALT_POLICY`, `VINU_KILL_SCOPE`, `VINU_LIVE_MAX_DAILY_LOSS_PCT` kept.
- Loop: `VINU_SLIPPAGE_FEEDBACK_ENABLED`, `VINU_SLIPPAGE_UPDATE_INTERVAL_DAYS`.
- Exec: `VINU_EXEC_PARTIAL_ENABLED`, `VINU_EXEC_MAX_PCT_OF_VOLUME`, `VINU_EXEC_TWAP_SLICES=6`, `VINU_EXEC_INVENTORY_SKEW_ENABLED`, `VINU_EXEC_IDEMPOTENCY_ENABLED`, `VINU_EXEC_BORROW_RATE`, `VINU_EXEC_CORP_ACTION_CHECK`.
- Guard kept: mandate `max_position_pct 0.25`, `max_order_value 50000`, `max_daily_orders 20`, throttle 10 per sec, daily SQLite.
- Future timeframe: same `VINU_SWEEP_INTERVALS` drives symbols, no extra knob. Fills same for 1D, 1H, 15min.

---

## Order to build (safety first, closed 9)

1. Fill parity spread queue latency + kill entries-only. 1-2 together. Honest + safe. Small.
2. Slippage loop + partial + idempotency + borrow. 3-4 + 8-9 together. Medium small. After 1 green.
3. Dry-run wallet + inventory skew. 6-7 together. After 2 green. Needs wallet store + skew param.
4. Test: sim live same fills replay, HALT crash exit allowed entry blocked, slippage updates monthly, partial splits remainder, retry no double, borrow blocked when rate high.

After 1-4, broker done. Next is 7 UI status. Different doc.

---
Link: UI status single view 3 gaps + 3 extras + 1 top is in `17-ui-status.md`. 16 -> 17 = broker -> UI closed.

---

## All covered proof (nothing missed for broker)

- Guard `order_guard.py:31,67`, kill `kill_switch.py`, mandate load, daily SQLite, throttle 10 per sec. All read.
- Exec `execution.py:33,67` TWAP VWAP quantize covered.
- Costs `costs.py:73`, simulator T+1, slippage 0.0005 covered gap 1.
- Breaker, book, reconcile same as `15` kept.
- Repos mapped: Nautilus fills catalog 5 here, Freqtrade dry-run wallet 6 here + leak guard pairlist lookahead done 08, Hummingbot skew 7 here, Qlib purge done 08, Lean cycle same as monitor. No new repo needed.
- Ledger `inefficiencies-A-J.md:F` allocator retry kept, H ref_id kept, I secrets kept.
- Slices `04:37-39` B risk gateway throttle + freeze + dry-run wallet kept. Row 12 kill policy here step 2. Row 5 sizing `13` kept.
- 09 top3, 10 knobs, 11 paper all 6, 12 seven-day 10, 13 risk full, 14 storage full, 15 monitor closed kept. 16 closes broker.
