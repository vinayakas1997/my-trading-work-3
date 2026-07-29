# DA-29 🟠 No Timeout on Symbol Fetch Futures

**Component:** `vinu-tools`
**Files Changed:** `engine.py`

## Problem

`ThreadPoolExecutor.submit()` + `as_completed()` followed by `future.result()` with **no timeout**. If a single symbol's candle fetch hangs (DNS, TCP timeout, upstream dead), the entire `process()` call hangs forever, blocking the worker thread and all queued jobs.

## Root Cause

Line 78: `table = future.result()` — no timeout argument passed.

## Solution

Add `timeout=120` to `future.result(timeout=120)`. If a fetch takes longer than 120 seconds, `TimeoutError` is raised, the future is skipped, and remaining symbols continue processing.

## Files Changed

| File | Change |
|------|--------|
| `engine.py:78` | `future.result()` → `future.result(timeout=120)` |

## Verification

68 tests pass.
