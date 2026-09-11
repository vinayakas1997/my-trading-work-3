# Plan - 03 Vectorbt Not Connected

Goal: Sweep 20 points in 10s vector, not 190s loop.

Files touched:
- `vinu-components/vinu-research/vinu_research/sweep_grid.py:86` loop -> vector.
- `vinu-components/vinu-research/vinu_research/sweep.py:135` POST per param -> batch.
- `vinu-components/vinu-agent/vinu_agent/tools/run_parameter_sweep_tool.py` pass-through.

Steps:
1. Wire vectorbt batch in sweep_grid, cap 20.
2. Keep rank by deflated Sharpe, completeness, PBO same.
3. Test 20pts crossover 10s vs 190s.
4. Update status/testing + 00-STATUS-ALL to doing/done.

Knobs: `VINU_SWEEP_USE_VECTORBT=true`, `VINU_RESEARCH_SWEEP_GRID_MAX_POINTS=20` (see 10).
Acceptance: 20pts <=15s, rank table same shape, PBO present with 2+ succeeds.
