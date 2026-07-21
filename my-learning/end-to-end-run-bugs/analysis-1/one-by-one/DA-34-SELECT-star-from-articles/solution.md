# DA-34 🟡 `SELECT * FROM articles` Fetches All 23 Columns
# DA-35 🟡 `SELECT *` on Threads/Snapshots Tables

**Component:** `vinu-news`
**Files Changed:** `repository.py`, `sqlite_backend.py`, `analyze.py`

## Problem

7 query sites used `SELECT *` on `articles` (23 columns, including heavy text fields like `summary` and JSON blobs like `entities_json`). 2 query sites used `SELECT *` on `story_threads` (10 columns), and 1 on `thread_daily_snapshots` (7 columns).

`SELECT *` is schema-unsafe — adding a column to a table silently changes query results. It also prevents future optimization (narrowing returned columns per query).

## Root Cause

Queries were written with `SELECT *` for convenience. The `ARTICLE_COLUMNS` tuple already existed for `INSERT` but was never reused for `SELECT`.

## Solution

1. **Defined column constants** for the remaining tables:
   - `THREAD_COLUMNS` — 10 columns for `story_threads`
   - `SNAPSHOT_COLUMNS` — 7 columns for `thread_daily_snapshots`

2. **Added string helpers**: `_ARTICLE_COLS`, `_ARTICLE_COLS_A` (with `a.` prefix for JOINs), `_THREAD_COLS`, `_SNAPSHOT_COLS`

3. **Replaced 11 `SELECT *`/`SELECT a.*` sites** with f-strings using the column constants:
   - `repository.py`: `get_active_threads`, `get_thread`, `get_thread_articles`, `get_thread_timeline`, `search_articles`, `get_news_for_ticker`, `get_news_for_date`, `get_high_impact` (8 sites)
   - `sqlite_backend.py`: `get_articles_since` (1 site)
   - `analyze.py`: `_resolve_article` (2 sites)

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `repository.py:26-39` | Added | `THREAD_COLUMNS`, `SNAPSHOT_COLUMNS`, `_ARTICLE_COLS_A`, `_THREAD_COLS`, `_SNAPSHOT_COLS` |
| `repository.py:166-207` | Changed | 4 methods: `SELECT *` → `SELECT {_THREAD_COLS}` / `{_ARTICLE_COLS}` / `{_SNAPSHOT_COLS}` |
| `repository.py:225-267` | Changed | 2 methods: `SELECT a.*` → `SELECT {_ARTICLE_COLS_A}` |
| `repository.py:276-305` | Changed | 2 methods: `SELECT *` → `SELECT {_ARTICLE_COLS}` |
| `sqlite_backend.py:11` | Added | Import `ARTICLE_COLUMNS` |
| `sqlite_backend.py:172-178` | Changed | `get_articles_since`: `SELECT *` → `SELECT {cols}` |
| `analyze.py:10` | Added | Import `ARTICLE_COLUMNS` |
| `analyze.py:53-66` | Changed | `_resolve_article`: 2 queries `SELECT *` → `SELECT {cols}` |

## Verification

52 news tests pass (0 failures). All existing queries exercise the modified code paths.
