# Testing - 19-portfolio (DD ladder)

Command: python3 -m pytest vinu-portfolio/tests/test_circuit_breakers.py vinu-portfolio/tests/test_drawdown_scheduler.py -q
Expected: 9 passed, ladder ok/halve/flat/halt.
Actual: 9 passed, 100 ok 95 ok 89 halve 84 flat 79 halt.
Status: green for ladder, red for regime pending.
Proof log: build output 2026-09-09.
Note: regime+sleeves pending separate.
