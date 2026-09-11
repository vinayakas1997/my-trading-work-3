# Plan - 08 Advanced Sweep (1+2 + 5 logics)

Goal: Fast + smart sweep, honest PBO.

Files touched:
- `vinu-components/vinu-research/vinu_research/sweep_grid.py:86` vectorbt 20pts 10s.
- `vinu-components/vinu-research/vinu_research/sweep.py` hyperopt 8pts + pairlist.
- `vinu-components/vinu-research/vinu_research/pbo.py` purge+embargo+triple-barrier.
- `vinu-components/vinu-simulator/tests/test_custom_sim.py` lookahead guard.
- `vinu-components/vinu-research/vinu_research/comparison.py:33` ensemble later.

Steps:
1. Vectorbt fast wire 20pts 10s.
2. Hyperopt 8 smart + pairlist vol filter.
3. Purge 5d + embargo + triple-barrier + lookahead test.
4. Notebook rank view, ensemble after green.

Knobs: `USE_VECTORBT`, `USE_HYPEROPT`, `HYPEROPT_MAX_POINTS=8`, `PURGE`, `TRIPLE_BARRIER` (see 10).
Acceptance: 8 tries 10s, PBO honest, no future leak, crowding visible.
