# Testing - 16-broker (fills+idempotency)

Command:
- python3 -m pytest vinu-simulator/tests/ -q -k "cost"
- python3 -m pytest vinu-live/tests/test_trade_plan_orchestrator.py -q
Expected: 10 passed + 30 passed, spread raises buy lowers sell.
Actual: 10 passed + 30 passed, base 1001.50 vs spread 1001.75, sell 998.25.
Status: green for fills+idempotency, red for rest.
Proof log: build output 2026-09-09.
Note: slippage loop + partial pending separate.
