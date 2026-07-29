# DA-11 🟠 All Stock-Price Routes Block ASGI Event Loop

**Component:** `vinu-stock-price`
**Files Changed:** None (false positive)

## Problem (as stated)

The audit claimed `GET /candles/{symbol}` reads parquet files, aggregates in Python, and computes indicators — all synchronously. "All route handlers are `def` (sync), meaning they block the uvicorn worker thread pool."

## Root Cause of Misdiagnosis

The audit confused "sync `def` handler" with "ASGI event loop blocking." In FastAPI:

- **`async def` handlers** run on the event loop thread — sync I/O inside them blocks the event loop
- **`def` (sync) handlers** are automatically dispatched to FastAPI's thread pool executor, keeping the event loop free

All 11 route handlers in `routes_read.py` and `routes_config.py` are already `def` (sync). The audit's recommended fix ("convert to `async def` + `run_in_executor") is exactly equivalent to the current code — just with more boilerplate.

## Investigation

| File | Route | Signature |
|------|-------|-----------|
| `routes_read.py:19` | `GET /health` | `def health()` |
| `routes_read.py:24` | `GET /catalog` | `def list_catalog()` |
| `routes_read.py:30` | `GET /catalog/{symbol}` | `def symbol_catalog()` |
| `routes_read.py:38` | `GET /candles/{symbol}` | `def candles()` |
| `routes_config.py:34` | `GET /settings` | `def read_settings()` |
| `routes_config.py:44` | `PATCH /settings` | `def patch_settings()` |
| `routes_config.py:58` | `GET /watchlist/tickers` | `def list_watchlist()` |
| `routes_config.py:63` | `POST /watchlist/tickers` | `def add_watchlist_tickers()` |
| `routes_config.py:69` | `DELETE /watchlist/tickers/{symbol}` | `def remove_watchlist_ticker()` |
| `routes_config.py:75` | `POST /watchlist/sync` | `def sync_watchlist()` |
| `routes_config.py:88` | `POST /backfill/trigger` | `def trigger_backfill()` (offloads to daemon thread) |
| `routes_config.py:129` | `GET /backfill/status/{job_id}` | `def backfill_status()` |
| `routes_config.py:138` | `POST /ingest/trigger` | `def trigger_ingest()` (offloads to daemon thread) |

Zero `async def` handlers found. All handlers use the correct FastAPI pattern for synchronous work.

## Verdict

**False positive.** Invalid. No change needed. The codebase already uses the optimal pattern for sync I/O in FastAPI.
