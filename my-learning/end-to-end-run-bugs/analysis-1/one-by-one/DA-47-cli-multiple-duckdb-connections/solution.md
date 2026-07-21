# DA-47 🟡 CLI Creates 3 DuckDB Connections Per 60s Cycle

**Component:** `vinu-stock-price`
**Files Changed:** `cli.py`

## Problem

Every 60-second ingest cycle created **3 separate `StockService()` instances**, each opening a new DuckDB connection:

1. `sync_and_backfill()` → `StockService()` → `duckdb.connect()` #1
2. `run_cycle()` → `StockService()` → `duckdb.connect()` #2
3. In-loop settings fetch → `StockService()` → `duckdb.connect()` #3

Each connection involved IPC overhead (DuckDB is in-process but creates threads and memory pools).

## Root Cause

The `while True` loop in `ingest_main()` called three nested functions, each of which created its own `StockService()` context manager. The loop body had no shared service instance.

## Solution

Restructured the loop to create **one** `StockService()` before the loop and pass it to the nested functions:

```python
with StockService() as service:
    while True:
        sync_and_backfill(service)
        run_cycle(service)
        sleep_sec = service.get_settings().poll_interval_sec
        logging.info("Sleeping %s seconds until next ingest", sleep_sec)
        time.sleep(sleep_sec)
```

The nested functions `run_cycle` and `sync_and_backfill` now accept a `service` parameter instead of creating their own.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `cli.py:86-114` | 28 → 24 | Moved `StockService()` outside the loop; pass `service` parameter to nested functions |

## Verification

33 stock-price tests pass (0 failures).
