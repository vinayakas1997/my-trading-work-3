# Testing - 15-monitor (HALT+time-stop+cooldown)

Command: python3 -m pytest vinu-live/tests/test_trade_plan_orchestrator.py -q
Expected: 30 passed, cooldown 2 losses locks entries exits never blocked.
Actual: 30 passed, 2 losses True lock 24h win False empty False.
Status: green for HALT+time-stop+cooldown, red for trailing/bracket pending.
Proof log: build output 2026-09-09.
Note: auth 2 fail pre-existing, not blocker.
