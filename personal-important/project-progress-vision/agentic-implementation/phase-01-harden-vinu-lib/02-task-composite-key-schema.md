# Task 2: Add Composite-PK Support to SQLiteBackend Schema

**Status:** DONE (already handled by Table DDL in subclasses)

## Purpose

Stock-price needs dedup on `(symbol, provider, bar_ts)` and news needs it on `(url, published_at)`. These are composite keys, not single-column primary keys. The `SQLiteBackend` already supports this via the existing `SCHEMA` DDL pattern — subclasses specify `PRIMARY KEY (col1, col2)` in their `SCHEMA` string, and the `upsert`/`insert_or_ignore` methods accept `conflict_columns: list[str]` which handles composite keys naturally.

## Findings

No code change is needed in `SQLiteBackend` itself. The class already:

1. Accepts any DDL in `SCHEMA` via `conn.executescript()`, so composite primary keys are supported via the standard SQL syntax.
2. The new `upsert()` and `insert_or_ignore()` methods accept `conflict_columns: list[str]` which works identically for composite keys.

Test coverage was added via the `CompositeKeyBackend` subclass in `test_sqlite.py` which creates a table with `PRIMARY KEY (key1, key2)` and tests both upsert and insert_or_ignore with `conflict_columns=["key1", "key2"]`.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-components/vinu-infra/tests/test_sqlite.py` | 12-22 | Added `CompositeKeyBackend` test subclass |
| `vinu-components/vinu-infra/tests/test_sqlite.py` | 130-165 | Added `test_upsert_composite_key` and `test_insert_or_ignore_composite_key` tests |

## Verification

- [x] Table with composite PK is created correctly via SCHEMA DDL
- [x] `upsert` with composite conflict_columns works
- [x] `insert_or_ignore` with composite conflict_columns works
