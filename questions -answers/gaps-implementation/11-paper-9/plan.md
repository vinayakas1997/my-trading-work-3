# Plan - 11 Paper 9 + Live

Goal: Store 9 BENCHING, paper all 9, promote best forward paper.

Files touched:
- `vinu-components/vinu-agent/vinu_agent/agent/research_artifact_writer.py:43` 1 to 9.
- `vinu-components/vinu-live/vinu_live/shadow_evaluator.py:28,44,92,97,122` paper-days + evaluate_all + promote.
- Config for `SHADOW_MIN_PAPER_DAYS`.

Steps:
1. Writer stores top3 per interval (9).
2. Paper-days knob 10 for 1D, 5 for 1H.
3. evaluate_all loops all, promote paper_sharpe>0 + degradation<=0.5.
4. Next analysis reads all 6/9 + full_progress view.

Knobs: `SHADOW_MIN_PAPER_DAYS`, `SHADOW_MIN_PAPER_DAYS_1D=10`, `_1H=5` (see 10).
Acceptance: 9 BENCHING papered, 1-2 ACTIVE best forward, rest backup.
