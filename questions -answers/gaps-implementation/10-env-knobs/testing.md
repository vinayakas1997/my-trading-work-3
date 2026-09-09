# Testing - 10-env-knobs (sweep subset)

Command:
- python3 -m pytest vinu-research/tests/test_config.py -q
- python3 -m pytest vinu-research/tests/ -q -k "sweep or grid or config"
Expected: 4 passed + 53 passed.
Actual: 4 passed + 53 passed.
Status: green for sweep subset, red for rest.
Proof log: build output 2026-09-09.
Note: .env-example + agent mirror pending separate test.
