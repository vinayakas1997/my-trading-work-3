# Testing - 20-learning (worker+decay)

Command:
- python3 -m pytest vinu-live/tests/test_feedback_loop.py -q
- python3 -m pytest vinu-research/tests/ -q -k "decay or executor or scheduled"
Expected: 16 + 67 passed, stale snapshot decayed.
Actual: 16 + 67 passed, 1 pre-existing lazy_init fail same on stash.
Status: green for worker+decay, red for PRIDE pending.
Proof log: build output 2026-09-09.
Note: PRIDE + regime lessons pending separate.
