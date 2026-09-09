# Testing - 10-env-knobs (sweep+docs)

Command:
- python3 -m pytest vinu-research/tests/test_config.py -q
- python3 -m pytest vinu-research/tests/ -q -k "sweep or grid or config"
- grep -c "VINU_" vinu-components/.env-example
Expected: 4 + 53 passed, knobs documented.
Actual: 4 + 53 passed earlier, 20 VINU_ lines now.
Status: green for sweep+docs, red for agent mirror pending.
Proof log: build output 2026-09-09.
Note: agent mirror pending separate.
