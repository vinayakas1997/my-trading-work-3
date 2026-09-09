# Status - 12-seven-day-10

Date: 2026-09-09
State: doing (trading-days+overlap done, pause/HRP pending)
Owner: agent build
Doing: rehearsal honest window done. Next auto-pause 3d + HRP last.
Done:
- loop.py: weekend step-back Friday, 7 calendar = 5 trading, overlap 1.0 + run_id + conditions.
Bugs found while implementing: none, rehearsal k=0 deselect, paper/loop 58 green.
Other files touched:
- vinu-components/vinu-research/vinu_research/loop.py:859
Next: partial size + HRP decision last.
Done2:
- shadow_evaluator.py: auto_paused when paper Sharpe <= -1.0 env, fast pause never promotes, 7 green.
