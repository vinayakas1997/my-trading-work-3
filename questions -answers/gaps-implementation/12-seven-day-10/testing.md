# Testing - 12-seven-day-10 (window+pause)

Command:
- python3 -m pytest vinu-research/tests/ -q -k "paper or loop"
- python3 -m pytest vinu-live/tests/test_shadow_evaluator*.py -q
Expected: 58 + 7 passed, auto_paused on deep negative.
Actual: 58 + 7 passed, art-bad auto_paused Sharpe <= -1.
Status: green for window+pause, red for HRP pending.
Proof log: build output 2026-09-09.
Note: HRP pending separate.
