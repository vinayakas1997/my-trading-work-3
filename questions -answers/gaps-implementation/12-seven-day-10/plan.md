# Plan - 12 Seven-Day 10 Points

Goal: Honest 7-day rehearsal + shadow promote + feedback close.

Files touched:
- `vinu-components/vinu-research/vinu_research/loop.py:704,835,899` rehearsal window + degrade 0.5.
- `vinu-components/vinu-research/vinu_research/config.py:153` trading days knob.
- `vinu-components/vinu-live/vinu_live/shadow_evaluator.py:28,92,97,122` paper days + absolute Sharpe.
- `vinu-components/vinu-simulator/engine/costs.py:73`, `simulator.py:103` fills.
- `vinu-components/vinu-live/feedback_loop.py:86` close learning.

Steps:
1. Trading days 5 not calendar 7 + overlap gap exclude tuning.
2. Paper 10/5 per interval + absolute paper_sharpe>0.3.
3. Fill spread+queue+latency + parity test + turbulence gate.
4. Partial size + auto-pause 3d + HRP decision last.

Knobs: paper-days, `WF_GAP_DAYS=5`, rehearsal lookback 7 (see 10).
Acceptance: overlap excluded, noisy 5d fixed, net honest, fast pause works.
