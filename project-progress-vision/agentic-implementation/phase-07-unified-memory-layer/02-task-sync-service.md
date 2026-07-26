# Task 2: Build SyncService

**Status:** DONE

## Purpose

Create the HTTP sync layer that pulls data from all upstream services into the `UnifiedMemoryStore`, giving the agent a local queryable cache of research runs, strategy artifacts, simulation results, stock-price summaries, and news articles.

## Approach

- `SyncService` takes a `UnifiedMemoryStore` and `services_config` dict
- Each sync method (`sync_research`, `sync_artifacts`, `sync_simulator`, `sync_stock_price`, `sync_news`) pulls from the corresponding HTTP endpoint and transforms into `MemoryEntry` objects
- `sync_symbol()` runs all five syncs for a single symbol
- `sync_all()` runs research + artifacts + simulator (no symbol needed)
- Each sync source clears its previous entries and rebuilds, ensuring consistency
- Errors are logged and caught — one failing source doesn't block others

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/memory/sync_service.py` | 1-290 | Created — SyncService with all sync methods |

## Verification

- [ ] sync_research pulls from GET /research/runs and creates entries with source="research"
- [ ] sync_artifacts pulls from GET /research/artifacts with status filter
- [ ] sync_simulator pulls from GET /runs and creates entries with source="simulator"
- [ ] sync_stock_price pulls from GET /candles/{symbol} and creates price_summary
- [ ] sync_news pulls from GET /search and creates news_article entries
- [ ] All syncs gracefully handle service unavailability (log warning, return 0)
