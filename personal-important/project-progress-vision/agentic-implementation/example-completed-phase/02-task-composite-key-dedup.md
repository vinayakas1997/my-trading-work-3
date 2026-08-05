# Task 2: Composite-Key Dedup in SQLiteBackend

**Status:** DONE

## Purpose

Stock-price needs dedup on `(symbol, provider, bar_ts)` — a composite key, not a single-column primary key. News needs dedup on `(url, published_at)`. Add schema-creation support for composite primary keys and composite conflict targets.

## Approach

Extend `SQLiteBackend`'s table-creation helper to accept a `composite_pk: list[str]` parameter. The `upsert` and `insert_or_ignore` methods already accept `conflict_columns: list[str]` which works for composite keys naturally.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-infra/sqlite.py` | 22-28 | Added `composite_pk` param to `ensure_table()` |
| `vinu-infra/tests/test_sqlite.py` | 80-105 | Added `TestCompositeKey` test class |

## Verification

- [x] Table created with correct composite PK constraint
- [x] `upsert` with composite conflict target works correctly
- [x] `insert_or_ignore` with composite conflict target works correctly
- [x] Backward compatible: single-column PK path unchanged
