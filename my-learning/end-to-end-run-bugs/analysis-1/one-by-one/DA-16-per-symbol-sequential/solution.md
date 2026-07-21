# DA-16 🟡 Per-Symbol Sequential HTTP for Price Data in Simulator

**Component:** `vinu-simulator`
**Files Changed:** `vinu_simulator/clients/price_client.py`

## Problem

Both `get_ohclv()` and `_fetch_price_data()` iterate over symbols ONE AT A TIME, making a separate HTTP request per symbol. For N symbols, there are N sequential round-trips. With 500 symbols at ~50ms latency, that's ~25 seconds of pure network wait.

## Root Cause

The loops had no parallelism — `for sym in symbols: self.get(...)` runs each request sequentially.

## Solution

Wrapped both loops in `ThreadPoolExecutor` (max_workers=8):

1. **Added import:** `from concurrent.futures import ThreadPoolExecutor, as_completed`

2. **`get_ohclv()`:** Sequential loop replaced with `pool.submit()` pattern. Each symbol request runs in a thread; results collected into `dict[str, DataFrame]`. `BaseClient.threading.local()` gives each worker thread its own `httpx.Client` automatically.

3. **`_fetch_price_data()`:** Same parallel pattern. Results appended to `all_dfs` list. Pivot + symbol validation (`missing` check) remain sequential (post-reduce).

## Verification

- Syntax check: `python -c "import ast; ast.parse(...)"` passes.
- At runtime: calling with 20+ symbols should complete in ~wall-clock time of the slowest single fetch, not sum of N fetches.
