# DA-55 🟡 vinu-tools features route has no retry

**Component:** `vinu-tools`
**Files Changed:** `vinu-tools/vinu_tools/server/routes_features.py`, `vinu-tools/vinu_tools/service.py`

## Problem

Two outbound HTTP calls in vinu-tools had no retry:
1. `routes_features.py:70-71` — async `httpx.AsyncClient` call to stock API for candle/indicator data. Failed immediately on transient errors.
2. `service.py:254-255` — health check `httpx.get()` with `except Exception: pass`. No retry on transient errors.

## Solution

### routes_features.py
Added async retry loop (3 attempts, exponential backoff 1.5x) wrapping the `httpx.AsyncClient` call. Retries on `httpx.TimeoutException`, `httpx.ConnectError`, and `httpx.HTTPStatusError` for 429/500/502/503/504. Non-retryable HTTP errors propagate immediately. The outer `try/except` still converts all remaining exceptions to `HTTPException(502)`.

### service.py
Added 3-attempt retry with exponential backoff to the health check `httpx.get()` call. On exhaustion, sets `stock_api_healthy = False` (existing fallback behavior).

### Files changed

| File | Change |
|------|--------|
| `vinu-tools/vinu_tools/server/routes_features.py` | Added async retry loop with 3x exponential backoff |
| `vinu-tools/vinu_tools/service.py` | Added retry loop to health check `httpx.get()` |

### Verification

1. `python -c "import ast; ast.parse(open('routes_features.py').read()); print('OK')"` ✓
2. `python -c "import ast; ast.parse(open('service.py').read()); print('OK')"` ✓
3. `from vinu_tools.server.routes_features import router` ✓
4. `from vinu_tools.service import FeatureService` ✓
