# Status - 08-advanced-sweep

Date: 2026-09-09
State: doing (step1+hyperopt done, purge pending)
Owner: agent build
Doing: fast + hyperopt done. Next purge+embargo+triple-barrier.
Done:
- step1 vectorbt-style batch done in sweep_grid.py (see 03).
- step2 hyperopt: oversized >20 subsamples to 8 when config on, no-config raises, 13 green.
Bugs found while implementing: first subsampled 12 to 8 broke tests, fixed to oversized + config-gated.
Other files touched:
- vinu-components/vinu-research/vinu_research/sweep_grid.py:39
Next: notebook rank view (view layer, CSV covers interim).
Done5:
- labels.py triple-barrier +1/-1/0 pure + 4 tests green.
Done4:
- lookahead verified: test_custom_sim future-fill guard 3 green (engine raises on bfill leak).
Done3:
- pbo.py: embargo_periods drops OOS block boundaries, env VINU_PBO_EMBARGO_PERIODS default 0 (WF gap 5d already purges), 46 green.
