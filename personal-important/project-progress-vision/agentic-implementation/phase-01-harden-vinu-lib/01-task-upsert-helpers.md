# Task 1: Add Upsert Helpers to SQLiteBackend

**Status:** DONE

## Purpose

Add `upsert()` and `insert_or_ignore()` convenience methods to `SQLiteBackend` so downstream callers don't need to hand-roll their own `INSERT ... ON CONFLICT` SQL. These are used by stock-price (catalog upsert_symbol), news (backfill_status upsert), and the future research catalog.

## Approach

Both methods build parameterized SQL with `ON CONFLICT (conflict_columns) DO UPDATE SET ...` and `ON CONFLICT ... DO NOTHING` respectively. They accept composite key columns via `conflict_columns: list[str]` which naturally handles both single and multi-column keys.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-components/vinu-infra/sqlite.py` | 52-78 | Added `upsert()` method |
| `vinu-components/vinu-infra/sqlite.py` | 80-99 | Added `insert_or_ignore()` method |

## Verification

- [x] `upsert` inserts new row when no conflict exists
- [x] `upsert` updates existing row when conflict exists
- [x] `upsert` with empty conflict_columns raises ValueError
- [x] `insert_or_ignore` inserts new row on first call, ignores on conflict
- [x] `upsert` with composite key works correctly
- [x] `insert_or_ignore` with composite key works correctly
