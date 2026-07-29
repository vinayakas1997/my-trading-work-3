# Task 6: Add Simulation Catalog Table to MetaStorage

**Status:** DONE

## Purpose

Add a `simulation_catalog` table to `vinu-simulator`'s `MetaStorage` that tracks per-symbol+strategy run count, last run/validated timestamps, last Sharpe and max drawdown. This mirrors the research catalog pattern and provides fast-lookup for "what simulations have been run for this symbol?"

## Approach

- New `simulation_catalog` table: `symbol TEXT, strategy_name TEXT, last_run_ts TEXT, last_validated_ts TEXT, run_count INTEGER, last_validation_verdict TEXT, last_sharpe REAL, last_max_dd REAL, PRIMARY KEY (symbol, strategy_name)`
- Table creation in `_ensure_simulation_catalog()` method called from `__init__`
- Uses `db.add_columns()` for future column additions (same pattern as `_ensure_config_hash_column`)
- Methods:
  - `upsert_catalog_entry(symbol, strategy_name, ...)` — upserts with `ON CONFLICT DO UPDATE SET` incrementing `run_count`
  - `get_catalog_entry(symbol, strategy_name)` — optionally scoped to strategy
  - `list_catalog()` — all entries sorted by symbol

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-simulator/vinu_simulator/storage/meta.py` | 1 | Added `timezone` import |
| `vinu-simulator/vinu_simulator/storage/meta.py` | 20-21 | Added `_ensure_simulation_catalog()` call in `__init__` |
| `vinu-simulator/vinu_simulator/storage/meta.py` | 58-117 | Added `_ensure_simulation_catalog`, `upsert_catalog_entry`, `get_catalog_entry`, `list_catalog` |

## Verification

- [x] `upsert_catalog_entry` creates new entry and increments run_count on subsequent calls
- [x] `get_catalog_entry(symbol)` returns latest entry by `last_run_ts`
- [x] `get_catalog_entry(symbol, strategy)` returns specific strategy entry
- [x] `get_catalog_entry` returns None for missing symbol
- [x] `list_catalog` returns all entries
