# Status - 10-env-knobs

Date: 2026-09-09
State: done (sweep+docs+mirror)
Owner: agent build
Doing: sweep intervals/topN/vectorbt/diversity wired to config.
Done:
- config.py: sweep_intervals, top_n, use_vectorbt, concurrency, hyperopt, diversity, min_succeeds + load_config.
- sweep_grid.py: use config when present, else env, order preserved.
Bugs found while implementing: none, env + config consistent.
Other files touched:
- vinu-components/vinu-research/vinu_research/config.py
- vinu-components/vinu-research/vinu_research/sweep_grid.py
Next: none, all closed.
Done2:
- .env-example: gap knobs section sweep/paper/DD/provider/fills/lesson/mute.
Done3:
- writer TOP_N mirror: reads TOP_N_PER_INTERVAL first TOP_N fallback, verified 2 cap. INTERVALS loop via sweep_interval_list 1d first.
Done4:
- .env-example gap section: all 37 knobs match code exactly, 2 wrong names fixed (DIVERSITY_REQUIRED, TOP_N_PER_INTERVAL), every name grep-verified.
