# Testing - 15-monitor (HALT+time-stop)

Command: python3 -m pytest vinu-live/tests/test_trade_plan_orchestrator.py -q
Expected: 30 passed (29 old + 1 new allows-exit).
Actual: 30 passed. Full live suite 169 passed + 2 auth pre-existing fail (same on stash).
Status: green for HALT+time-stop, red for rest.
Proof log: build output 2026-09-09.
Note: auth 2 fail pre-existing, not blocker.
