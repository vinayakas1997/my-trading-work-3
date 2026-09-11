# Plan - 14 Storage 3x Full

Goal: Backtest + rehearsal + paper same shape, tiny KBs.

Files touched:
- `vinu-components/vinu-simulator/storage/results.py:45,48,62,79` equity/trades/weights/meta.
- `vinu-components/vinu-simulator/models/metrics.py:8` 30 metrics.
- `vinu-components/vinu-simulator/engine/validation.py:9` Monte Carlo + walk.
- `vinu-components/vinu-research/models.py:625` PaperRehearsalResult +4 fields run_id/regime/conditions/overlap.
- `vinu-components/vinu-research/loop.py:835,867` keep run_id + regime + overlap.
- `vinu-components/vinu-live/vinu_live/shadow_evaluator.py:44` paper regime.
- `notebooks/rehearsal_compare.py` 4-col view.

Steps:
1. Models add 4 fields, old tests pass.
2. Loop returns full for top3 per interval.
3. Paper same shape, promote rule kept.
4. Notebook + tests link loads equity.

Knobs: `REHEARSAL_STORE_FULL`, `REGIME_ENABLED`, `OVERLAP_ENABLED` (see 10).
Acceptance: run_id loads equity, regime present, overlap 0.2s, 18 stores per ticker.
