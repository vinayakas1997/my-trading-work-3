# Testing - 15-monitor (HALT+time-stop+cooldown+trailing+turbulence)

Command: python3 -m pytest vinu-live/tests/test_trade_plan_orchestrator.py -q
Expected: 30 passed, trailing 117/121, calm False wild True.
Actual: 30 passed, all verified.
Status: green for 4/5, red for bracket pending (schema change).
Proof log: build output 2026-09-09.
Note: auth 2 fail pre-existing, not blocker.
