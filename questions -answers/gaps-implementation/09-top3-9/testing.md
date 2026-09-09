# Testing - 09-top3-9 (diversity)

Command:
- python3 -m pytest vinu-research/tests/ -q -k "comparison or rank"
- python diversity check 3 crossover + 1 rsi -> diverse [crossover,rsi,crossover fill]
Expected: 24 passed, diverse never 3 same when 3+ shapes exist.
Actual: 24 passed, diverse ok.
Status: green for diversity, red for writer 9 pending.
Proof log: build output 2026-09-09.
Note: writer 9 needs separate test when built.
