# Task 4: Integration Gap Check — stock-price & news coverage

**Status:** DONE

## Purpose

Verify that `SQLiteBackend` + `ParquetStore` (after Tasks 1-3) cover all usage patterns currently used by `vinu-stock-price`'s `CatalogStore`/parquet storage and `vinu-news`'s `BackfillStore`. Any gap found here would be fixed in this phase before declaring it done.

## Approach

Read through stock-price's `CatalogStore` and parquet storage, and news's `BackfillStore` and repository storage. Map every public method to vinu-infra equivalents. Identify uncovered patterns.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| (none) | — | Analysis-only task |

## Findings

| Package | Pattern | Covered? | Notes |
|---------|---------|----------|-------|
| stock-price catalog | `upsert_symbol` with composite key `(symbol, provider)` | Yes | Task 1's `upsert()` with `conflict_columns=["symbol", "provider"]` |
| stock-price catalog | Job table `INSERT OR IGNORE (symbol, year)` | Yes | Task 1's `insert_or_ignore()` |
| stock-price catalog | Migration tracking (`_ensure_*_column`) | Yes | Already supported by existing `SQLiteBackend.MIGRATIONS` + `db.add_columns()` |
| stock-price parquet | `write_bars()` full rewrite | Yes | Vinu-lib's `append()` with merge covers this |
| stock-price parquet | `append_bars()` daily shard pattern | Yes | Use `append()` with shard path like `live/AAPL_20260701.parquet` |
| stock-price parquet | `read_bars()` base + shards union | Yes | Task 3's `read_shard()` with glob pattern |
| stock-price parquet | `consolidate_live_shards()` merge + delete | Yes | Task 3's `consolidate()` |
| stock-price parquet | Domain-specific dedup on `(symbol, provider, bar_ts)` | Partial | vinu-infra uses generic column-based dedup via pandas `drop_duplicates`. Stock-price has optimized tuple-key dedup. The generic approach works correctly but may be slightly slower. Acceptable for Phase 1; optimization can be done later if needed. |
| news backfill | `upsert(ticker, **fields)` dynamic columns | Yes | Task 1's `upsert()` with explicit column dict handles this |
| news backfill | `ensure_ticker` creates-if-not-exists | Yes | Task 1's `insert_or_ignore()` |
| news repository | Thread-local connections + WAL | Yes | Already provided by `SQLiteBackend._get_conn()` |
| news repository | Inline migrations via `_migrate()` | Yes | `db.add_columns()` is drop-in replacement for manual `PRAGMA table_info` + `ALTER TABLE` |

**Gap: SettingsStore and WatchlistStore.** Both stock-price and news have nearly identical key-value settings tables and ticker watchlist tables. These are lightweight (2-3 methods each). They could be moved into vinu-infra as generic utilities in a later phase, but it's not a blocker — they're small enough to remain package-local for now.

**Conclusion:** No hard gaps found. Phase 1 primitives cover everything needed for downstream phases.

## Verification

- [x] All stock-price catalog methods mapped to vinu-infra equivalents
- [x] All stock-price parquet operations covered by Task 3 additions
- [x] All news backfill methods mapped to vinu-infra equivalents
- [x] No missing primitives identified
- [x] SettingsStore/WatchlistStore noted as optional future cleanup, not a blocker
