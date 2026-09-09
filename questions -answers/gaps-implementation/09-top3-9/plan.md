# Plan - 09 Top3 9 Per Ticker

Goal: 1D top3 + 1H top3 + 15min top3 = 9 BENCHING per ticker, 27 total.

Files touched:
- `vinu-components/vinu-research/vinu_research/comparison.py:19` rank + diversity filter.
- `vinu-components/vinu-agent/vinu_agent/agent/research_artifact_writer.py:43` write 9 not 1.
- `vinu-components/vinu-simulator/vinu_simulator/engine/regime.py` regime tag.
- `vinu-components/vinu-infra/freeze.py` data hash.
- `vinu-components/vinu-research/gates/correlation_gate.py:34` corr 0.85.
- `vinu-components/vinu-research/scheduled/executor.py:148` decay 30d.

Steps:
1. Diversity: best per shape, never 3 same.
2. Regime tag trend/range/high-vol per artifact.
3. Freeze hash required, corr gate, 7d rehearsal cost-aware.
4. Decay promote rank2 on 0.5 drop.

Knobs: `SWEEP_INTERVALS=1d,1H,15min`, `TOP_N=3`, `DIVERSITY`, `REGIME_TAG`, `FREEZE_REQUIRED` (see 10).
Acceptance: 9 BENCHING per ticker with tags, notebook table Sharpe vs DD vs rank.
