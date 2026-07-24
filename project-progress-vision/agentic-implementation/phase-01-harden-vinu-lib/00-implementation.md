# Phase 01: Harden vinu-lib Primitives

**Status:** COMPLETED
**Started:** 2026-07-24
**Depends on:** —
**Blocks:** Phase 02 (research/simulator catalog), Phase 05 (migrate stock-price & news)

## What It Delivers

`vinu-lib`'s `SQLiteBackend` and `ParquetStore` are hardened with the missing primitives that downstream packages need:

- **SQLiteBackend**: upsert helpers (`upsert()` and `insert_or_ignore()`), composite-key support in schema creation, exposed `_get_conn()` for sub-store composition
- **ParquetStore**: sharded writes (`write_shard`), shard reads (`read_shard`), consolidation (`consolidate`)

These additions close the gap between what vinu-lib provides and what stock-price/news/research actually need, so downstream phases can build on a single shared foundation instead of hand-rolling duplicates.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-components/vinu-lib/sqlite.py` | vinu-lib | modify |
| `vinu-components/vinu-lib/parquet.py` | vinu-lib | modify |
| `vinu-components/vinu-lib/tests/test_sqlite.py` | vinu-lib | modify |
| `vinu-components/vinu-lib/tests/test_parquet.py` | vinu-lib | modify |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-upsert-helpers.md` | Add `upsert()` and `insert_or_ignore()` to SQLiteBackend | DONE |
| 2 | `02-task-composite-key-schema.md` | Add `composite_pk` param to SQLiteBackend's schema creation | DONE |
| 3 | `03-task-sharded-parquet-writes.md` | Add `write_shard()`, `read_shard()`, `consolidate()` to ParquetStore | DONE |
| 4 | `04-task-integration-gap-check.md` | Verify coverage against stock-price/news patterns | DONE |

## Dependencies Met

- [x] No dependencies — this is the foundation phase
