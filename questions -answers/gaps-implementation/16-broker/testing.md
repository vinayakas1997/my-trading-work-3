# Testing - 16-broker (fills+idempotency+partial)

Command:
- python3 -m pytest vinu-simulator/tests/ -q -k "cost"
- python3 -m pytest vinu-live/tests/test_trade_plan_orchestrator.py -q
- python3 -m pytest vinu-live/tests/ -q -k "scheduler or execution"
Expected: 10 + 30 + 19 passed, partial continues on failure.
Actual: 10 + 30 + 19 passed.
Status: green for fills+idempotency+partial, red for slippage/borrow pending.
Proof log: build output 2026-09-09.
Note: slippage loop + borrow pending separate.
