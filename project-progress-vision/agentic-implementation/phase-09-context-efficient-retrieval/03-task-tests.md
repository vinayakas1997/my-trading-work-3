# Task 3: Tests for Phase 09

## Track A Tests (vinu-agent)

Existing tests pass (24/24 in `test_unified_memory.py`):
- `test_list_by_symbol` — updated to use unique source_ids per entry so dedup doesn't collapse results

Key behaviors verified:
- `list_by_symbol` still returns correct entries per symbol
- All search/filter/count operations unchanged
- Dedup not triggered for unique source_ids

## Track B Tests (vinu-research)

Existing test outcomes:
- `test_sqlite_backend.py` — 12/13 pass, 1 pre-existing Windows failure (`test_concurrent_writes`: SQLite locked on Win32)
- `test_catalog.py` — all 11 tests fail pre-existing on Windows (PermissionError during temp dir cleanup due to SQLite handle held open)
- `test_loop.py` — all pass
- `test_service.py` — all pass

## Manual verification

The following scenarios were manually verified:

**Track A:**
- `UnifiedMemoryStore.scored_search` returns entries sorted by composite score
- Dedup by `(source, source_id)` filters true duplicates
- `ContextBuilder` budget enforcement truncates memory when above `max_memory_tokens`
- Symbol extraction still works the same way

**Track B:**
- `ResearchStorage.update_catalog_after_run` correctly increments counters
- `ResearchStorage.is_symbol_exhausted` returns True for exhausted/over-researched symbols
- `StrategyResearchLoop.run` early-exits when symbol is exhausted
- Service passes `validated=True` when holdout/stress test passes
