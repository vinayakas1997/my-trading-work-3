# DA-31 🟠 Upstream Errors Silently Return 200 OK With Empty Data

**Component:** `vinu-tools`
**Files Changed:** `routes_features.py`, `test_api.py`

## Problem

The `except` block in `GET /features/{symbol_or_kind}` caught all upstream errors (timeout, DNS failure, HTTP 500, parse error) and returned **200 OK** with `{"values": {}, "signal": 0.0}`. Downstream services (strategy, portfolio) could not distinguish "no data" from "upstream is down."

## Root Cause

A bare `except Exception` at the bottom of the handler returned a 200 with empty data instead of propagating the error.

## Solution

Replace the 200 return with `raise HTTPException(status_code=502, detail=f"Upstream stock-api error for {symbol}: {exc}")`. This lets callers distinguish "stock has no data" (200, empty) from "upstream is unreachable" (502).

## Files Changed

| File | Change |
|------|--------|
| `routes_features.py:93-97` | `return {...}` → `raise HTTPException(502, detail=...)` |
| `test_api.py:74-90` | Added `test_feature_for_symbol_upstream_error` verifying 502 |

## Verification

69 tests pass including the new error-case test.
