# Testing - 07-sweep-7 (all 7)

Command:
- python3 -m pytest vinu-agent/tests/test_phase1_sweep_tool_scoping.py -q
- python3 -m pytest vinu-research/tests/ -q -k "sweep or grid"
- python3 -m pytest vinu-agent/tests/ -q -k "triage or planner or thesis or gate"
- python3 -m pytest vinu-research/tests/test_config.py -q
Expected: 5 + 35 + 90 + 4 passed, human bypasses K-cap, intervals 1d first.
Actual: 5 + 35 + 90 + 4 passed, machine False human True, [1d,1H,15min].
Status: green all 7.
Proof log: build output 2026-09-09.
Note: 07 closed.
