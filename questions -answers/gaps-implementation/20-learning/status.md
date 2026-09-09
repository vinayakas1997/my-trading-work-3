# Status - 20-learning

Date: 2026-09-09
State: done (worker+decay+STAR+context; full feed deferred with entry)
Owner: agent build
Doing: all closed. Full market-regime feed join entry: price history in live (have last5+halted context now).
Done:
- lesson_worker.py: counts closed_positions, LESSON after 30, env MIN_TRADES/INTERVAL, live book 1 closed -> skipped_not_enough correct.
- Calibration wire already exists scheduler_workers low_trust 0.45, never gated.
Bugs found while implementing: table is closed_positions not positions, fixed.
Other files touched:
- vinu-components/vinu-live/vinu_live/lesson_worker.py (new)
Next: full market-regime feed join (needs price history in live).
Done4:
- lesson_worker.py: last5 W/L + halted context per lesson, live L/False verified.
Done2:
- executor.py: single decay policy VINU_DECAY_RATIO 0.5 + VINU_DECAY_FORGET_DAYS 90 stale decayed, 67 green (1 pre-existing lazy_init fail same on stash).
Done3:
- lesson_worker.py: STAR prefix closed>=50 env, verified names.
