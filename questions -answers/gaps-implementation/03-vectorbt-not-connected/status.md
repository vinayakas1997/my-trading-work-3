# Status - 03-vectorbt-not-connected

Date: 2026-09-09
State: done (fast path wired, vectorbt-style batch)
Owner: agent build
Doing: -
Done:
- sweep_grid.py: USE_VECTORBT env + semaphore 5 gather, order preserved.
- Rollback false = sequential old path.
Bugs found while implementing: none, shared ResearchTools handles concurrent.
Other files touched:
- vinu-components/vinu-research/vinu_research/sweep_grid.py:44,130
Next: 08 step2 hyperopt, 09 writer 9.
