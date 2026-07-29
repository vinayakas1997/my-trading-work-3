# DA-50 🟠 vinu-strategy BaseClient returns `{}` on HTTP error

**Component:** `vinu-strategy`
**Files Changed:** `vinu-strategy/clients/base.py`

## Problem

`BaseClient._get()` and `_post()` silently return `{}` on every HTTP error. Callers (`service.py`) use the results without checking for failure — when vinu-tools or vinu-initial-analysis are briefly down, features and correlation signals silently degrade to empty data, producing wrong trading signals.

## Root Cause

BaseClient was written as a "best effort" wrapper — catch every exception, return empty dict, let the pipeline continue. No retry mechanism existed for transient failures (HTTP 503, timeout, connection reset).

## Solution

Replaced the separate `_get()` and `_post()` with a shared `_request(method, path, **kwargs)` that implements:

1. **Exponential backoff retry** — 3 attempts (`delay = 1.0 * 1.5^attempt`) on `httpx.TimeoutException`, `httpx.ConnectError`, and HTTP 429/500/502/503/504
2. **Status code logging** — every warning now includes the HTTP status code (e.g. `"HTTP error on GET ... (status 503)"`)
3. **Non-transient errors** — HTTP 4xx still return `{}` with a warning (client errors shouldn't be retried)
4. **Unexpected errors** — caught by `except Exception` and returned as `{}` with an error log (last-resort safety net)

### Retry flow

```
GET /features/AAPL → 503 (retry 1/3 after 1.0s)
GET /features/AAPL → 503 (retry 2/3 after 1.5s)
GET /features/AAPL → 200 OK → return data ✓
```

### Files changed

| File | Change |
|------|--------|
| `vinu-strategy/clients/base.py` | Added `_request()` with retry, `_get()`/`_post()` now delegate to it |

### Verification

1. `python -c "import ast; ast.parse(open('vinu-strategy/clients/base.py').read()); print('syntax OK')"` — passes
2. `from vinu_strategy.clients.base import BaseClient` — resolves correctly
3. `from vinu_lib.retry import TransientProviderError` — dependency on DA-48 fix confirmed
