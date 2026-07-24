# Task 4: Integration Gap Check — stock-price & news coverage

**Status:** DONE

## Purpose

Verify that `SQLiteBackend` + `ParquetStore` (after Tasks 1-3) cover **all** usage patterns currently used by `vinu-stock-price`'s `CatalogStore`/parquet storage and `vinu-news`'s `BackfillStore`. Any gap found here is fixed before declaring Phase 1 done.

## Approach

Read through `vinu-stock-price/vinu_stock/catalog/store.py`, `vinu-stock-price/vinu_stock/storage/parquet.py`, `vinu-news/vinu_news/backfill/store.py`, and `vinu-news/vinu_news/analysis/storage/` — catalog every public method, its params, and its SQL/parquet operations. Cross-reference against `SQLiteBackend` and `ParquetStore` APIs.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| (none) | — | This task is analysis-only; no code changes |

## Findings

| Package | Pattern | Covered? | Notes |
|---------|---------|----------|-------|
| stock-price catalog | `upsert_symbol` with composite key `(symbol, provider)` | Yes | Task 1 + Task 2 |
| stock-price catalog | Job table `INSERT OR IGNORE (symbol, year)` | Yes | Task 1's `insert_or_ignore` |
| stock-price catalog | Migration tracking (`_ensure_*_column`) | Yes | Already supported by existing `SQLiteBackend.MIGRATIONS` pattern |
| stock-price parquet | `write_bars()` year-file + daily shard layout | Yes | Task 3 |
| stock-price parquet | `consolidate_live_shards()` | Yes | Task 3's `consolidate()` |
| news catalog | `backfill_status` with watermark updates per chunk | Yes | Task 1's `upsert` |
| news catalog | Permanent failure marking | Yes | Standard SQL update via existing `execute()` |
| news storage | URL-level + semantic dedup | Partial | URL-level dedup covered (composite key). Semantic dedup (story-thread matching) is higher-level logic that belongs in the news package, not in vinu-lib. No gap. |

**Conclusion:** No gaps found. Phase 1 primitives cover everything needed.

## Verification

- [x] All stock-price catalog methods mapped to vinu-lib equivalents
- [x] All news backfill/storage methods mapped to vinu-lib equivalents
- [x] No missing primitives identified
