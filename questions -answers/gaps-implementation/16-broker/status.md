# Status - 16-broker

Date: 2026-09-09
State: doing (fills+idempotency done, rest open)
Owner: agent build
Doing: fill parity + idempotency done. Next slippage loop + partial + borrow.
Done:
- costs.py: spread_bps + queue_pct both models, env defaults 0 keep old, honest when set.
- orchestrator.py: _submit_order client_order_id artifact+symbol+side+qty+minute, env toggle.
Bugs found while implementing: none, defaults keep backward compat.
Other files touched:
- vinu-components/vinu-simulator/vinu_simulator/engine/costs.py
- vinu-components/vinu-live/vinu_live/trade_plan/orchestrator.py
Next: slippage feedback monthly, borrow/corp check.
Done2:
- scheduler.py: slice client_order_id idempotency + partial summary log, remainder next cycle via reconciler, 19 green.
