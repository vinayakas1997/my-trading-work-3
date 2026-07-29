# DA-30 🟠 Sync HTTP Call in Sync Route Blocks ASGI

**Component:** `vinu-tools`
**Files Changed:** `routes_features.py`, `test_api.py`

## Problem

`GET /features/{symbol_or_kind}` was a sync `def` handler that called `httpx.get()` synchronously inside it. This blocked a FastAPI threadpool worker for the duration of the HTTP round-trip to vinu-stock-price.

## Root Cause

The handler was defined as `def` (sync) and used `httpx.get()` (sync HTTP call). FastAPI runs sync handlers in a threadpool (not the event loop), but the sync HTTP call still occupies that worker thread unnecessarily during I/O wait.

## Solution

- Changed `def get_feature_or_symbol()` → `async def get_feature_or_symbol()`
- Replaced `httpx.get(url, ...)` with `async with httpx.AsyncClient() as client: await client.get(url, ...)`
- Moved `import httpx` from inside the function body to top-of-file imports

## Files Changed

| File | Change |
|------|--------|
| `routes_features.py:9,33,70-71` | Top-level `import httpx`; `def`→`async def`; `httpx.get()`→`httpx.AsyncClient().get()` |
| `test_api.py:3,41-69` | Added `test_feature_for_symbol` with mocked `AsyncClient` |

## Verification

68 tests pass, including the new test that verifies the `/features/{symbol}` endpoint returns parsed candle data correctly.
