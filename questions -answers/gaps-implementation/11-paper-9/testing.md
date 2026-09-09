# Testing - 11-paper-9 (paper-days knob)

Command: python3 -m pytest vinu-live/tests/ -q -k "shadow"
Expected: 10 passed, per-interval threshold works, default 5 kept.
Actual: 10 passed.
Status: green for knob, red for writer 9 pending.
Proof log: build output 2026-09-09.
Note: writer 9 needs separate test when built.
