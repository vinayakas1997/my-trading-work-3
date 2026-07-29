# BUG-01 🔴 NaN in JSON Responses

**Component:** `vinu-lib`
**Files Changed:** `vinu-lib/vinu_lib/server.py`
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

The research API returned `POST /research/run 500` with JSON serialization errors because
backtest metrics contained `NaN` values (e.g., Sharpe ratio, win rate when trade count is 0).
`json.dumps` cannot serialize `float('nan')` by default.

Example: When a backtest produces 0 trades, metrics like Sharpe ratio are NaN, and the
response fails to serialize.

## Root Cause

Python's `json.dumps` does not handle `float('nan')`, `float('inf')`, or `float('-inf')`.
The research pipeline returns backtest metrics that can legitimately be NaN (e.g., no trades
executed), but no serialization guard existed.

## Suggested Fix

Add `allow_nan=True` to `json.dumps` calls globally, or replace NaN values with `null`
before serialization.

## Actual Fix

A global monkey-patch was added at the top of `vinu_lib/server.py`:

```python
import json
json.encoder.FLOAT_REPR = lambda o: ...  # Not used
# Instead, a custom JSON encoder or the built-in allow_nan=False + custom default
```

The fix replaces `NaN` with `None` in all response data before serialization, so
`json.dumps` outputs `null` instead of raising.

## Verification

1. Run `POST /research/run` with a strategy that produces 0 trades
2. Confirm response 200 (not 500) with `"sharpe_ratio": null`
3. Run with a strategy that produces trades — confirm normal response

## Lessons Learned

- Always handle NaN/Infinity in numeric responses
- Use custom JSON encoder or pre-process data before serialization
- Test edge cases: 0 trades, all-NaN metrics, empty universes
