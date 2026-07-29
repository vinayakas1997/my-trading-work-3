# DA-19 🟡 BaseClient Thread Lock Serializes Concurrent Requests

**Component:** `vinu-simulator`
**Files Changed:** `clients/base.py`

## Problem

`BaseClient` wrapped every HTTP call in `self._lock` — a single `threading.Lock()` protecting a shared `httpx.Client`. The simulator API runs via `asyncio.get_event_loop().run_in_executor()`, dispatching work to a thread pool. This means multiple simulations can run concurrently. The lock serialized ALL HTTP calls globally: if Simulation A was fetching AAPL prices, Simulation B blocked waiting for MSFT prices.

## Root Cause

`httpx.Client` is not thread-safe, so some form of serialization is required. The original design used one lock per `BaseClient` instance, which meant only one thread could use the client at a time — even for unrelated symbols.

## Fix

Replaced the single shared `httpx.Client` + lock with a **thread-local client** pattern:

```python
self._local = threading.local()

def _client(self) -> httpx.Client:
    if not hasattr(self._local, "client"):
        self._local.client = httpx.Client(timeout=self._timeout)
    return self._local.client
```

- each thread lazily creates its own `httpx.Client` on first use
- no lock needed — threads don't share client instances
- `close()` only closes the current thread's client (if it was created)
- connection pooling still works per-thread

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `base.py:3` | Added | `import threading` |
| `base.py:12-14` | Changed | `self._client` + `self._lock` → `self._local = threading.local()` |
| `base.py:16-19` | Added | `_client()` method — lazy thread-local client creation |
| `base.py:24-27` | Changed | `get()` — removed `with self._lock:`, use `self._client()` |
| `base.py:29-32` | Changed | `post()` — removed `with self._lock:`, use `self._client()` |
| `base.py:34-37` | Changed | `close()` — safely close current thread's client if any |

## Verification

92 simulator tests pass (0 failures). Thread-local client creation is exercised by test fixtures that create `BaseClient` subclasses.
