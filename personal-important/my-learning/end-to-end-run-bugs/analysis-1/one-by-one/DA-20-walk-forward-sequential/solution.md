# DA-20 🟡 Walk-Forward Windows Run Sequentially

**Component:** `vinu-research`
**Files Changed:** `loop.py`

## Problem

`_run_walk_forward()` iterated windows with a sequential `for w in windows` loop. Each window runs 2 backtests (in-sample + out-of-sample). With 3 default windows, that's 6 sequential HTTP calls — each waiting for the previous to complete.

Windows are fully independent (different date ranges, same strategy code, no shared state).

## Solution

Extracted per-window work into an inner async helper `_run_window(w)` and parallelized with `asyncio.gather()`:

- Each window's IS + OOS backtests run concurrently via `asyncio.gather()`
- All windows run concurrently via outer `asyncio.gather()`
- `return_exceptions=True` handles partial failures gracefully (failed windows are skipped)
- Result filtering with `isinstance(r, dict)` preserves the same behavior as before (skip None/exceptions)

## File Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py:1` | Added | `import asyncio` |
| `loop.py:552-598` | Replaced | Sequential `for w in windows` → `_run_window()` async helper + `asyncio.gather()` |

## Verification

369 tests pass (2 pre-existing failures only). Same aggregate metrics — the output is identical, just computed in parallel.
