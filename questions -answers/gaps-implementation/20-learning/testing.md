# Testing - 20-learning (lesson v1)

Command:
- python3 -m pytest vinu-live/tests/test_feedback_loop.py -q
- python3 -c "from vinu_live.lesson_worker import cycle; print(cycle())"
Expected: 16 passed, cycle skipped_not_enough closed 1.
Actual: 16 passed, skipped_not_enough closed 1 correct.
Status: green for worker, red for decay/PRIDE pending.
Proof log: build output 2026-09-09.
Note: decay + PRIDE pending separate.
