# Plan - 16 Broker Fills

Goal: Sim = live fills, safe kill, no double.

Files touched:
- `vinu-components/vinu-simulator/engine/costs.py:73`, `simulator.py:103` spread+queue+latency.
- `vinu-components/vinu-agent/vinu_agent/broker/order_guard.py:31,16`, `kill_switch.py` HALT entries-only, scope symbol.
- `vinu-components/vinu-live/vinu_live/execution.py:33,67` TWAP/VWAP + partial + idempotency + borrow.
- Slippage feedback monthly job.

Steps:
1. Fill parity spread/queue/latency + kill entries-only. Honest + safe.
2. Slippage loop + partial split + idempotency key + borrow/corp check.
3. Dry-run wallet + inventory skew. After 2 green.
4. Tests: replay same fills, HALT exit allowed, no double, borrow blocked.

Knobs: SPREAD_BPS, QUEUE_PCT, LATENCY_MS, HALT_POLICY, PARTIAL, IDEMPOTENCY, BORROW (see 10).
Acceptance: rehearsal pass = live slip 0.2-0.5 accounted, no double fill.
