# Phase 01: Harden vinu-lib Primitives (Example)

**Status:** COMPLETED
**Started:** 2026-07-24
**Depends on:** —
**Blocks:** Phase 02, Phase 05

## What It Delivers

`vinu-lib`'s `SQLiteBackend` and `ParquetStore` are hardened with the missing primitives that stock-price/news need (upsert helpers, composite-key dedup, sharded parquet writes), thoroughly tested, and ready to serve as the shared foundation for everything downstream.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-lib/sqlite.py` | vinu-lib | modify |
| `vinu-lib/parquet.py` | vinu-lib | modify |
| `vinu-lib/tests/test_sqlite.py` | vinu-lib | modify |
| `vinu-lib/tests/test_parquet.py` | vinu-lib | modify |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-upsert-helpers.md` | Add `upsert()` and `insert_or_ignore()` to SQLiteBackend | DONE |
| 2 | `02-task-composite-key-dedup.md` | Support composite-key dedup in SQLiteBackend schema helper | DONE |
| 3 | `03-task-sharded-parquet-writes.md` | Add `write_shard()`/`consolidate()` to ParquetStore | DONE |
| 4 | `04-task-integration-gap-check.md` | Verify SQLiteBackend/ParquetStore cover all stock-price/news usage patterns | DONE |

## Dependencies Met

- [ ] No dependencies — this is the foundation phase

## Verification

- [x] All four tasks completed
- [x] All existing vinu-lib tests pass
- [x] New tests for upsert, composite-key dedup, and sharded writes pass
- [x] Manual check: `vinu-stock-price`'s existing usage patterns are coverable without additional changes to vinu-lib
- [x] `status.md` updated
