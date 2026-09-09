# Status - 10-env-knobs

Date: 2026-09-09
State: doing (sweep knobs wired, rest open)
Owner: agent build
Doing: sweep intervals/topN/vectorbt/diversity wired to config.
Done:
- config.py: sweep_intervals, top_n, use_vectorbt, concurrency, hyperopt, diversity, min_succeeds + load_config.
- sweep_grid.py: use config when present, else env, order preserved.
Bugs found while implementing: none, env + config consistent.
Other files touched:
- vinu-components/vinu-research/vinu_research/config.py
- vinu-components/vinu-research/vinu_research/sweep_grid.py
Next: .env-example docs + agent config mirror + INTERVALS loop.
