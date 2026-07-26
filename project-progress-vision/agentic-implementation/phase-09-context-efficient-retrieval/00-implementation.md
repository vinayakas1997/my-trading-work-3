# Phase 09: Context-Efficient Retrieval + Overfitting/Robustness

**Status:** IN PROGRESS
**Started:** 2026-07-26
**Depends on:** Step 7 (unified memory layer), Step 2 (catalog)
**Blocks:** Step 11 (integration testing)

## What It Delivers

Two parallel sub-tracks:

**Track A — Context-Efficient Retrieval:** Smart scoring, dedup, and context-budget management for the agent's memory retrieval. The `UnifiedMemoryStore` now returns relevance-ranked results (combining FTS rank, recency, and source importance), deduplicates entries by source+source_id, and the `ContextBuilder` enforces a token budget to prevent memory context from crowding out the actual conversation.

**Track B — Overfitting/Robustness:** Adds validation tracking fields to `research_catalog` (`total_validated_count`, `last_validation_verdict`, `consecutive_validation_failures`, `exhausted`), an exhaustion check that auto-STOPs symbols that repeatedly fail validation with too few lifetime trials, and updates `update_catalog_after_run` to track validation results.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-agent/vinu_agent/memory/unified_store.py` | vinu-agent | modify (scored search, dedup) |
| `vinu-agent/vinu_agent/agent/context.py` | vinu-agent | modify (context budget, dedup) |
| `vinu-research/vinu_research/storage/sqlite_backend.py` | vinu-research | modify (catalog fields + exhaustion check) |
| `vinu-research/vinu_research/loop.py` | vinu-research | modify (exhaustion check in risk critic) |
| `vinu-research/vinu_research/service.py` | vinu-research | modify (pass validation to catalog) |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-track-a-retrieval.md` | Scored search, dedup, context budget for agent memory | DONE |
| 2 | `02-track-b-overfitting.md` | Validation tracking in catalog + exhaustion check | DONE |
| 3 | `03-task-tests.md` | Tests for both tracks | DONE |

## Dependencies Met

- [x] Step 7 completed — UnifiedMemoryStore and context injection exist
- [x] Step 2 completed — research_catalog with lifetime_trial_count
- [x] Step 3 completed — MC validation verdicts computed
- [x] Step 6 completed — cross-run comparison uses catalog data
