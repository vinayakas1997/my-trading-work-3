# Phase 12: Shadow/Live Validation

**Status:** COMPLETED
**Started:** 2026-07-26
**Depends on:** Step 2 (research_catalog with `last_validated_ts`)
**Blocks:** Phase 13

## What It Delivers

Continuous re-validation of ACTIVE/MONITORING strategies against fresh data using the `last_validated_ts` watermark. Detects strategy decay before it becomes critical by periodically re-backtesting artifacts and running Monte Carlo validation.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_research/models.py` | vinu-research | modify — added `last_validated_ts`, `revalidation_count`, `last_revalidation_verdict` to `Artifact` |
| `vinu_research/config.py` | vinu-research | modify — added `revalidation_interval_days`, `revalidation_lookback_days` |
| `vinu_research/service.py` | vinu-research | modify — added `revalidate_artifact()` method |
| `vinu_research/storage/strategy_store.py` | vinu-research | modify — schema migration, `list_stale_artifacts()`, updated `upsert_artifact`/`_row_to_artifact` |
| `vinu_research/storage/sqlite_backend.py` | vinu-research | modify — added `touch_catalog_validated_ts()` |
| `vinu_research/scheduled/executor.py` | vinu-research | modify — added `revalidation_scan()`, wired into `_run_loop` |
| `tests/test_decay.py` | vinu-research | modify — added 4 new tests |
| `tests/test_sqlite_backend.py` | vinu-research | modify — added `TestCatalogRevalidation` (3 tests) |
| `tests/test_service.py` | vinu-research | modify — added `TestRevalidate` (2 tests) |
| `tests/test_scheduled.py` | vinu-research | modify — added 2 new tests |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | — | Add re-validation tracking fields to Artifact model + DB migration | DONE |
| 2 | — | Build `revalidate_artifact()` in ResearchService | DONE |
| 3 | — | Wire `revalidation_scan()` into ScheduledResearchExecutor | DONE |
| 4 | — | Add `touch_catalog_validated_ts()` to ResearchStorage | DONE |
| 5 | — | 11 new tests for all new functionality | DONE |

## Dependencies Met

- [x] Step 2 completed — `research_catalog` with `last_validated_ts` watermark
- [x] All prior phases complete
