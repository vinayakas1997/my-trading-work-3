# Phase 02: Research/Simulator Catalog + Checkpoint Tables

**Status:** COMPLETED
**Started:** 2026-07-24
**Depends on:** Phase 01 (hardened vinu-lib primitives)
**Blocks:** Phase 04 (wire Monte Carlo gate), Phase 06 (comparative critique agent)

## What It Delivers

Built on top of Step 1's hardened `vinu_lib.SQLiteBackend`, this phase delivers:

1. **Research catalog** (`research_catalog` table) — one row per symbol tracking lifetime trial count, last run ID/timestamp, last validated timestamp, best Sharpe ever, and status. Replaces what 01-vision-plan Phase 1's storage design and Phase 3 were separately trying to build.

2. **Iteration checkpoints** (`iteration_checkpoints` table) — per-iteration persistence with idempotent `INSERT OR IGNORE` keyed on `(run_id, iteration)`. Enables crash-resume (Phase 04 will wire the resume logic) and gives the comparative critique agent (Phase 06) structured cross-run history to query.

3. **Simulator catalog** (`simulation_catalog` table) — per-symbol+strategy tracking of run count, last run/validated timestamps, last Sharpe and max DD.

4. **Catalog update in service layer** — after each successful research run, the catalog is updated with trial count, best Sharpe, and timestamps.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-research/vinu_research/storage/sqlite_backend.py` | vinu-research | modify — refactored to extend `SQLiteBackend`, added catalog + checkpoint tables/methods |
| `vinu-research/vinu_research/loop.py` | vinu-research | modify — added `storage` param, checkpoint saving after each iteration |
| `vinu-research/vinu_research/service.py` | vinu-research | modify — pass storage to loop, update catalog after run completes |
| `vinu-simulator/vinu_simulator/storage/meta.py` | vinu-simulator | modify — added `simulation_catalog` table + CRUD methods |
| `vinu-research/tests/test_catalog.py` | vinu-research | create — 10 new tests for catalog and checkpoint methods |
| `vinu-simulator/tests/test_sim_catalog.py` | vinu-simulator | create — 5 new tests for simulator catalog |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-refactor-storage.md` | Refactor ResearchStorage to extend SQLiteBackend | DONE |
| 2 | `02-task-catalog-table.md` | Add research_catalog table + CRUD methods | DONE |
| 3 | `03-task-checkpoint-table.md` | Add iteration_checkpoints table + CRUD methods | DONE |
| 4 | `04-task-loop-checkpoints.md` | Add storage param to loop, save checkpoints per iteration | DONE |
| 5 | `05-task-service-catalog-update.md` | Update catalog after run completes in service layer | DONE |
| 6 | `06-task-simulator-catalog.md` | Add simulation_catalog table to MetaStorage | DONE |
| 7 | `07-task-tests.md` | Write tests for catalog + checkpoint + simulator catalog | DONE |

## Dependencies Met

- [x] Phase 01 completed (SQLiteBackend has upsert/insert_or_ignore + composite keys)

## Verification

- [x] 101 vinu-research tests pass (91 existing + 10 new)
- [x] 17 vinu-simulator tests pass (12 existing + 5 new)
- [x] All existing tests unchanged — zero regressions
- [x] ResearchStorage refactoring backward-compatible (same API surface)

## Review Findings & Fixes Applied (2026-07-24, separate review session)

An independent review of this phase found `lifetime_trial_count` was silently wrong in a
subtle way — not a crash, a bad value that the tests didn't catch:

- **Root cause**: in `ResearchService`, `prior_trials` (fetched via
  `self._storage.cumulative_trial_count(symbol)`) was only computed **inside**
  `if result.best_result:`. A research run that produced no passing candidate skipped that
  block entirely, so `prior_trials` stayed at its `0` default, and the symbol's lifetime trial
  count got overwritten with just that one failed run's iteration count — discarding every
  prior run's contribution.
- **Test masked it**: `test_update_catalog_updates_existing` in `tests/test_catalog.py`
  happened to pass either way, because it only exercises `update_catalog_after_run` directly
  with pre-computed totals — it never exercised the `service.py` code path where the bug
  actually lived.
- **Fix**: `prior_trials = await self._run_in_thread(self._storage.cumulative_trial_count, symbol)`
  moved out of the `if result.best_result:` block in `vinu_research/service.py`, so it's always
  correctly populated regardless of whether the run produced a passing candidate.
- **Also tightened**: `update_catalog_after_run` in `sqlite_backend.py` now has an explicit
  docstring clarifying that `trial_count` must already be the caller-computed lifetime total
  (not a per-run delta — adding here on top of an already-cumulative value would double-count),
  and `best_sharpe_ever` now correctly uses `MAX(best_sharpe_ever, excluded.best_sharpe_ever)`
  instead of a plain overwrite (a real, separate bug: the field is named "ever" but was being
  reset to whatever the latest run's Sharpe happened to be, even if lower than a prior run's
  best). Added `test_update_catalog_best_sharpe_ever_does_not_regress` to
  `tests/test_catalog.py` to cover the case the original tests missed (Sharpe decreasing between
  runs).
- **Suite after fix**: 407/407 vinu-research + 126/126 vinu-simulator tests pass.
