# Task 2: Add Research Catalog Table + CRUD Methods

**Status:** DONE

## Purpose

Create a `research_catalog` table (one row per symbol) that provides fast-lookup for: lifetime trial count, last run ID/timestamp, last validated timestamp, best Sharpe ever, and status. This replaces the expensive `SELECT SUM(total_iterations) ... WHERE symbol=?` pattern with a single row lookup.

## Approach

- Table schema in `_SCHEMA`: `symbol TEXT PRIMARY KEY, lifetime_trial_count INTEGER, last_run_id INTEGER, last_run_ts TEXT, last_validated_ts TEXT, best_sharpe_ever REAL, status TEXT`
- Methods:
  - `update_catalog_after_run(symbol, run_id, trial_count, sharpe, validated)` — upserts a catalog row with current run data
  - `get_catalog_entry(symbol)` — returns a single row or None
  - `list_catalog()` — all entries sorted by symbol
  - `list_stale_catalog(days)` — entries with `last_validated_ts` older than N days or NULL

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/storage/sqlite_backend.py` | 248-290 | Added `update_catalog_after_run`, `get_catalog_entry`, `list_catalog`, `list_stale_catalog` |

## Verification

- [x] `update_catalog_after_run` creates new entry for unseen symbol
- [x] `update_catalog_after_run` updates existing entry (trial count, sharpe)
- [x] `get_catalog_entry` returns None for missing symbol
- [x] `list_catalog` returns all entries
- [x] `list_stale_catalog(days)` correctly filters by staleness
