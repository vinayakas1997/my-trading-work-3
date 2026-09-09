# Testing - 15-monitor (HALT+time-stop+cooldown+trailing)

Command: python3 -m pytest vinu-live/tests/test_trade_plan_orchestrator.py -q
Expected: 30 passed, trailing long 117 short 121 nodata None.
Actual: 30 passed, trailing verified.
Status: green for HALT+time-stop+cooldown+trailing, red for bracket/turbulence pending.
Proof log: build output 2026-09-09.
Note: auth 2 fail pre-existing, not blocker.
