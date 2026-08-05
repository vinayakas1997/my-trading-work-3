# DA-15 🟡 Strategy Service Has No Warm-Up Mechanism

**Component:** `vinu-strategy`
**Files Changed:** `server/app.py`

## Problem

Zero work happened at process startup. The entire `StrategyAPI → StrategyService → Registry → Storage` chain was lazily created via `_get_api()` on the first HTTP request. Cold-start penalty: ~10-100ms for YAML parsing + SQLite setup + connection pooling to upstream services.

This was the **only** component in the codebase still using lazy initialization without eager creation — all others (vinu-news, vinu-stock-price, vinu-initial-analysis, vinu-tools, vinu-research) already eagerly create their service in `create_app()`.

## Solution

Added a `lifespan` hook to `app.py` that eagerly calls `_get_api()` during FastAPI startup via `asyncio.to_thread()`. The `vinu_infra/server.py` `create_app()` already supports a `lifespan` parameter — app.py just wasn't using it.

```python
@asynccontextmanager
async def lifespan(app):
    from vinu_strategy.server.routes_read import _get_api
    await asyncio.to_thread(_get_api)
    yield
```

- `asyncio.to_thread()` runs the sync `_get_api()` in a thread pool so startup doesn't block the event loop
- If init fails, the error surfaces at startup (fast failure) instead of on the first request
- Zero changes to routes_read.py or any other file

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `server/app.py:3-4,6-7` | Added | `import asyncio`, `from contextlib import asynccontextmanager` |
| `server/app.py:9-14` | Added | `lifespan()` async context manager with eager `_get_api()` call |
| `server/app.py:30` | Changed | Passed `lifespan=lifespan` to `_create_app()` |

## Verification

63 tests pass (1 pre-existing failure in test_expression.py unrelated).
