# Task 5: Update Catalog After Run Completes in Service Layer

**Status:** DONE

## Purpose

After a research run completes successfully, update the `research_catalog` entry for the symbol with the run's results (trial count, best Sharpe, validation status). This makes the catalog a live, queryable summary of all research activity.

## Approach

- In `ResearchService.run_research()`, pass `storage` to `StrategyResearchLoop`
- After the run completes and the run record is updated (line `await self._storage.update_run(record)`), call `self._storage.update_catalog_after_run(...)` with the cumulative trial count (prior_trials + total_iterations), run ID, best Sharpe, and validated flag
- Also pass `storage` to loop in `refresh_strategy()` for consistency

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/service.py` | 133, 183-189 | Pass `storage` to loop; add catalog update after run completes |
| `vinu-research/vinu_research/service.py` | 369 | Pass `storage` to loop in `refresh_strategy()` |

## Verification

- [x] `storage` parameter passed to `StrategyResearchLoop` in both `run_research` and `refresh_strategy`
- [x] Catalog updated after successful run completion
- [x] Cumulative trial count correctly aggregated (prior + current)
