# Testing - 07-sweep-7 (No.4+No.2)

Command:
- python3 -m pytest vinu-agent/tests/test_phase1_sweep_tool_scoping.py -q
- python3 -m pytest vinu-research/tests/ -q -k "sweep or grid"
Expected: 5 passed + 35 passed, no regression. Prompt mentions BASE_CODE.
Actual:
- 5 passed in 0.25s
- 35 passed, 595 deselected
Status: green (No.4+No.2 done, rest open).
Proof log: build output 2026-09-09, prompts contain BASE_CODE Path C.
Note: No.5/No.1/No.6/No.7 still open, test separately when done.
