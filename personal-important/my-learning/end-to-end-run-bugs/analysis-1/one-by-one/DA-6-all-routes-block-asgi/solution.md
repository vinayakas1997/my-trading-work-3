# DA-6 🟠 All API Routes Block ASGI Event Loop

**Component:** `vinu-initial-analysis`
**Files Changed:** `routes_read.py`, `routes_config.py` — removed `async` from all route handler defs

## Problem

All 14 route handlers are `async def`, but every one calls synchronous blocking code (HTTP via `requests`, CPU-bound ML training, parquet I/O, SQLite). FastAPI runs `async def` handlers directly on the event loop, so each request freezes the single-threaded event loop for its entire duration.

## Root Cause

`async def` route handlers calling synchronous service methods without `await`.

## Solution

Changed `async def` → `def` on all 14 route handlers (10 in `routes_read.py`, 2 in `routes_config.py`, plus 2 previously missed in `routes_config.py`). FastAPI automatically wraps plain `def` handlers with `run_in_executor()`, offloading them to a threadpool and freeing the event loop.

## Verification

All 60 tests pass (2 skipped).
