# Plan - 10 Env Knobs

Goal: Full control via .env, no code change for intervals.

Files touched:
- `.env-example:206` new sweep section, `.env` values.
- `vinu-components/vinu-research/vinu_research/config.py:192` load_config.
- `vinu-components/vinu-agent/vinu_agent/config.py:41` AgentConfig.
- `sweep_grid.py:86`, `comparison.py:19`, `correlation_gate.py:34`, `freeze.py`, `executor.py:148`.
- `backtest_runner/prompt.md:12` inject INTERVALS, not hard 1d.

Steps:
1. Add 10 new env + docs.
2. Wire INTERVALS loop per interval, TOP_N write 3.
3. Wire flags diversity/PBO/corr/freeze/revalidation.
4. Test: change INTERVALS, restart, 15min appears no rebuild.

Knobs: full 36 list in ../10-env-knobs.md. Core `SWEEP_INTERVALS=1d,1H,15min`, `TOP_N=3`.
Acceptance: env flip + restart changes sweep, no code edit.
