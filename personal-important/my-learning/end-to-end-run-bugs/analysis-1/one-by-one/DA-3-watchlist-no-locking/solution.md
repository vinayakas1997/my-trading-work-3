# DA-3 🔴 Watchlist Shared File Has No Locking (Data Loss)

**Component:** `vinu-news`, `vinu-stock-price` (shared watchlist)
**Files Changed:**
- `vinu-news/vinu_news/watchlist/shared.py` — atomic writes + file locking
- `vinu-stock-price/vinu_stock/watchlist/shared.py` — same changes (identical module)
- `vinu-news/pyproject.toml` — added `filelock>=3.0` dependency
- `vinu-stock-price/pyproject.toml` — added `filelock>=3.0` dependency
- `vinu-news/tests/test_watchlist_sync.py` — added 3 tests for atomic/safety
- `vinu-stock-price/tests/test_watchlist_sync.py` — added 3 tests for atomic/safety

## Problem

`write_shared()` used `path.write_text(json.dumps(data))` — non-atomic, no file lock. Up to 4 concurrent writers (news-ingest, news-api, stock-ingest, stock-api) could lose tickers via write-write race. A crash mid-write could corrupt the file (torn write).

## Root Cause

The shared JSON file had zero synchronization — no advisory locking, no atomic rename. Every writer directly overwrote the file with `write_text()`, which truncates then writes.

## Solution

1. **Atomic writes:** `write_shared()` now writes to a `.tmp` file, then `os.replace()` (atomic on POSIX) renames it to the target. A crash mid-write leaves the original file intact.

2. **File locking:** Both `read_shared()` and `write_shared()` acquire a `FileLock` on `<path>.lock` using the `filelock` library. The lock is held for the entire read/write, preventing concurrent access.

3. **Corrupted file handling:** `read_shared()` catches `JSONDecodeError` and returns `[]` instead of crashing.

4. **Dependencies:** Added `filelock>=3.0` to both `pyproject.toml` files.

## Verification

- All 10 watchlist sync tests pass (5 per component)
- Tests verify: atomic write (`.tmp` cleaned up), corrupted JSON returns `[]`, missing file returns `[]`
- Full test suite: 117 passed
