# Testing - 07-sweep-7 (No.4+No.2+No.5+No.6)

Command:
- python3 -m pytest vinu-agent/tests/test_phase1_sweep_tool_scoping.py -q
- python3 -m pytest vinu-research/tests/ -q -k "sweep or grid"
- python3 -m pytest vinu-agent/tests/ -q -k "triage or planner"
Expected: 5 + 35 + 51 passed, angle fit trend->crossover.
Actual: 5 + 35 + 51 passed, angle fit verified.
Status: green for No.4+No.2+No.5+No.6, red for No.1/No.7 pending.
Proof log: build output 2026-09-09.
Note: No.1/No.7 pending separate.
