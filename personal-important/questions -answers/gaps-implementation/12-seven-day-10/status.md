# Status - 12-seven-day-10

Date: 2026-09-09
State: done (window+pause; HRP deferred with entry criteria)
Owner: agent build
Doing: window + pause closed. HRP entry 30 trades + 60d live.
Done:
- loop.py: weekend step-back Friday, 7 calendar = 5 trading, overlap 1.0 + run_id + conditions.
Bugs found while implementing: none, rehearsal k=0 deselect, paper/loop 58 green.
Other files touched:
- vinu-components/vinu-research/vinu_research/loop.py:859
Next: none, window+pause closed. HRP + partial-size entries below.
Done2:
- shadow_evaluator.py: auto_paused when paper Sharpe <= -1.0 env, fast pause never promotes, 7 green.
HRP deferred (entry: 30 closed trades + 60d live; have 1 closed, 0d live). Partial fills covered by 16 (slices continue + remainder next cycle).
