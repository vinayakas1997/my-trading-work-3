# Task 4: Add Storage Param to Loop + Save Checkpoints

**Status:** DONE

## Purpose

Wire the checkpoint system into `StrategyResearchLoop` so that every iteration's result is persisted to the `iteration_checkpoints` table. The loop already accumulates iteration history in memory (`history: list[IterationRecord]`); this adds a parallel persistence step that survives process restarts.

## Approach

- Add optional `storage: ResearchStorage | None` parameter to `StrategyResearchLoop.__init__()`
- After each `history.append(record)` in `run()`, call `self._storage.save_checkpoint(...)` with the iteration number, strategy code, key metrics (Sharpe, Max DD, trade count), and critic verdict
- Checkpoint saving is conditional on `self._storage is not None and self._run_id > 0`
- Future Phase 04 will add the resume-from-last-checkpoint logic when a run restarts

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/loop.py` | 11 | Added import for `ResearchStorage` |
| `vinu-research/vinu_research/loop.py` | 119-142 | Added `storage: ResearchStorage | None` parameter to `__init__` |
| `vinu-research/vinu_research/loop.py` | 403-410 | Added `save_checkpoint()` call after `history.append()` |

## Verification

- [x] Loop still functions without storage (backward compatible — `storage` defaults to `None`)
- [x] When storage is provided, checkpoint is saved after each iteration
- [x] Metrics are serialized correctly (Sharpe, Max DD, trade count as JSON dict)
