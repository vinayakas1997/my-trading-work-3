# Task 1: Refactor ResearchStorage to Extend SQLiteBackend

**Status:** DONE

## Purpose

Replace `ResearchStorage`'s hand-rolled thread-local SQLite connection management with the shared `vinu_lib.SQLiteBackend` base class hardened in Phase 01. This eliminates a duplicated implementation of the same pattern and gives `ResearchStorage` access to `upsert()` and `insert_or_ignore()` for the new catalog and checkpoint tables.

## Approach

- `ResearchStorage` now inherits from `SQLiteBackend`
- The existing `_SCHEMA` string becomes the class attribute `SCHEMA`
- The existing inline `_migrate_schema()` (checking `PRAGMA table_info` and adding columns) becomes a `MIGRATIONS` list using `ALTER TABLE ADD COLUMN` — `SQLiteBackend`'s `_init_schema()` handles both via `conn.executescript(SCHEMA)` + `db.migrate_schema(conn, SCHEMA_VERSION, MIGRATIONS)`
- New tables (`research_catalog`, `iteration_checkpoints`) are added to the `SCHEMA` string alongside the existing `research_runs` table

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/storage/sqlite_backend.py` | 1-60 | Refactored `ResearchStorage` to extend `SQLiteBackend`; schema + migrations as class attributes; added catalog + checkpoint tables to SCHEMA |

## Verification

- [x] All existing `ResearchStorage` tests pass (16 tests in `test_sqlite_backend.py`)
- [x] `ResearchStorage()` still works with existing callers (same constructor signature)
- [x] Thread-safety preserved (WAL + thread-local connections from `SQLiteBackend`)
- [x] Schema migration backward compatible — existing `research_runs` table keeps all columns
