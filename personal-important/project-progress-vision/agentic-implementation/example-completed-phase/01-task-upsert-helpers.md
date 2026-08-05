# Task 1: Add Upsert Helpers to SQLiteBackend

**Status:** DONE

## Purpose

Add `upsert()` and `insert_or_ignore()` convenience methods to `SQLiteBackend` so downstream callers (stock-price's `CatalogStore`, news's `BackfillStore`, and the future research catalog) don't each hand-roll their own `INSERT ... ON CONFLICT` statements.

## Approach

Following the existing pattern in `sqlite.py`: a method on `SQLiteBackend` that accepts table name, data dict, and conflict columns, then builds and executes the `INSERT ... ON CONFLICT ... DO UPDATE/SET NOTHING` statement. Reuses the existing thread-safe WAL connection pool.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-infra/sqlite.py` | 89-112 | Added `upsert(table, data, conflict_columns)` method |
| `vinu-infra/sqlite.py` | 113-124 | Added `insert_or_ignore(table, data, conflict_columns)` method |
| `vinu-infra/tests/test_sqlite.py` | 45-78 | Added `TestUpsertHelpers` test class |

## Verification

- [x] Unit tests pass: upsert updates existing row, insert_or_ignore skips on conflict
- [x] Thread-safety test: concurrent upserts from multiple threads don't deadlock
- [x] Edge case: empty conflict_columns raises ValueError
