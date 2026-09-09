# Testing - 19-portfolio (ladder+per-symbol+hysteresis)

Command:
- python3 -m pytest vinu-portfolio/tests/test_circuit_breakers.py vinu-portfolio/tests/test_drawdown_scheduler.py -q
- python3 -m pytest vinu-portfolio/tests/ -q
Expected: 9 + 118 passed, hysteresis holds noise.
Actual: 9 + 118 passed, auth 2 pre-existing fail same on stash.
Status: green for ladder+per-symbol+hysteresis, red for sleeves pending.
Proof log: build output 2026-09-09.
Note: sleeves pending separate.
