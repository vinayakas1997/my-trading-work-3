# Phase 1 — Consolidate onto `vinu-lib`'s Shared Storage Primitives

Status: **not started** · Depends on: — · Blocks: Phase 2

## What it is

Makes `vinu-lib`'s `SQLiteBackend` (`vinu-lib/sqlite.py`) and `ParquetStore`
(`vinu-lib/parquet.py`) the actual shared foundation for the catalog/backfill pattern that
`vinu-stock-price` and `vinu-news` each currently implement independently by hand. Both
packages' designs are good — this phase does not change their behavior, data layout, or API
surface. It replaces their duplicated low-level plumbing (thread-local WAL SQLite connections,
schema migration bookkeeping, dedup-on-write parquet logic) with calls into the one
already-built, already-tested library that was clearly designed for exactly this.

Confirmed today: `grep -rl "SQLiteBackend\|ParquetStore"` across the repo shows these classes
are referenced **only in `vinu-lib`'s own tests**. `vinu-stock-price`'s `CatalogStore` and
`vinu-news`'s `BackfillStore` each open their own `sqlite3.connect`, manage their own WAL mode
and thread-local state, and hand-roll their own migration/version tracking. Same for parquet:
`vinu_stock/storage/parquet.py`'s dedupe-and-write logic and `vinu-lib/parquet.py`'s
`ParquetStore.append(..., dedup_on=[...])` do the same job with separately-maintained code.

## Impact

**Before this phase:** Two independently-debugged, subtly-different implementations of the
same catalog/dedup pattern exist. A bug fix or improvement (e.g., a smarter WAL checkpoint
policy, a better dedup collision strategy) applied to one package doesn't benefit the other.
Any *new* package needing this pattern (the research/simulator storage from
[phase-02](phase-02-research-simulator-catalog.md)) is at risk of becoming a third
reimplementation.

**After this phase:** One tested, shared implementation. Future improvements to
storage/backfill mechanics get written once and benefit every consumer. `phase-02`'s new
research/simulator catalog can be built directly on this base from day one instead of copying
a pattern by hand a third time.

**What still won't work after this phase alone:** This phase is purely a migration — no new
capability ships. It doesn't yet add a catalog to `vinu-simulator`/`vinu-research` (that's
Phase 2), and it doesn't yet build any cross-package memory view (Phase 3).

## Where changes occur

- `vinu-lib/sqlite.py` — review `SQLiteBackend` against what `CatalogStore`/`BackfillStore`
  actually need; it's likely already sufficient (thread-local WAL connections, `SCHEMA`/
  `SCHEMA_VERSION`/`MIGRATIONS` class-attribute pattern, `health_info()`), but confirm no gaps
  exist (e.g. `INSERT OR IGNORE`/upsert helpers, composite-key dedup support) before migrating
  callers onto it — add what's missing here rather than working around it downstream.
- `vinu-lib/parquet.py` — same review for `ParquetStore.append(rel_path, records,
  dedup_on=[...])`/`read()`/`compact()` against `vinu_stock/storage/parquet.py`'s
  `write_bars()`/`append_bars()`/`consolidate_live_shards()` feature set (year-file writes, daily
  live shards, shard consolidation). If `ParquetStore` doesn't yet support sharded/consolidatable
  writes, that's new work in `vinu-lib` before stock-price can migrate onto it without losing a
  capability it currently has.
- `vinu-stock-price/vinu_stock/catalog/store.py` — `CatalogStore` becomes a thin subclass/wrapper
  around `SQLiteBackend`, keeping its existing public methods (`upsert_symbol`, job-table
  methods) and schema (`schema.sql`) unchanged so no caller elsewhere in `vinu-stock-price` needs
  to change.
- `vinu-stock-price/vinu_stock/storage/parquet.py` — `write_bars`/`append_bars`/
  `consolidate_live_shards` reimplemented in terms of `ParquetStore`, preserving today's file
  layout (`{data_root}/prices/1m/{SYMBOL}/archive|live/...`) exactly.
- `vinu-news/vinu_news/backfill/store.py` — `BackfillStore` becomes a thin subclass/wrapper
  around `SQLiteBackend`, same schema, same public methods.
- `vinu-news/vinu_news/analysis/storage/` — SQLite-backed article storage migrated the same way.

## How to test it

- **No behavior-change tests are the primary bar here**: existing `vinu-stock-price/tests/` and
  `vinu-news/tests/` (whatever backfill/catalog/storage coverage already exists — confirm scope
  at implementation time) must continue to pass unmodified against the migrated implementation.
  This phase should not require rewriting existing test assertions, only possibly their setup/
  mocking if internals changed.
- New `vinu-lib/tests/` coverage for any gaps found and filled in `SQLiteBackend`/`ParquetStore`
  during the review step above (e.g. new upsert/dedup helpers).
- A migration-safety test: run the migrated `CatalogStore`/`BackfillStore` against an existing
  pre-migration `meta.db`/`backfill.db` file from a real (or realistic synthetic) prior version,
  confirming schema/data compatibility — this pattern already exists for `vinu-simulator`'s
  `_ensure_config_hash_column`-style migrations and should be followed here too.
- Manual smoke test: run stock-price's and news's backfill CLIs end to end against a small
  synthetic symbol/ticker range post-migration, confirming resumability (kill mid-run, restart,
  confirm it picks up from the watermark) still works exactly as before.
