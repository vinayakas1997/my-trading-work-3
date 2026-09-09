# Testing - 14-storage-3x (models+loop+paper)

Command:
- python3 -m pytest vinu-research/tests/ -q -k "rehearsal or model"
- python3 -m pytest vinu-research/tests/ -q -k "paper or loop or rehearsal"
- python3 -m pytest vinu-agent/tests/ -q -k "performance"
Expected: 16 + 58 + 2 passed, paper same shape.
Actual: 16 + 58 + 2 passed.
Status: green for models+loop+paper, red for notebook pending.
Proof log: build output 2026-09-09.
Note: notebook pending separate.
