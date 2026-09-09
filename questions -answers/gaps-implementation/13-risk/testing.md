# Testing - 13-risk (tail+vol)

Command: python3 -m pytest vinu-agent/tests/ -q -k "position or sizing or risk"
Expected: 38 passed, cvar 0.04 blocks 0, vol 0.30 halves 6250 to 3125.
Actual: 38 passed, cvar True/False ok, vol 0.5/1.0 ok, kelly 6250 vol-scaled 3125 blocked 0.
Status: green for tail+vol, red for BL/HRP later.
Proof log: build output 2026-09-09.
Note: hook wiring to pass cvar/vol pending separate.
