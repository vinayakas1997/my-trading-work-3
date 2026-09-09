# Testing - 14-storage-3x (models+loop)

Command:
- python3 -m pytest vinu-research/tests/ -q -k "rehearsal or model"
- python3 -m pytest vinu-research/tests/ -q -k "paper or loop or rehearsal"
Expected: 16 + 58 passed, regime tagged.
Actual: 16 + 58 passed 1 skipped.
Status: green for models+loop, red for paper+notebook pending.
Proof log: build output 2026-09-09.
Note: paper + notebook pending separate.
