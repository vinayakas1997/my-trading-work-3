# Chapter 27 — In-memory cache layer

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/cache.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch22 |

## 1. Problem

Correlation queries can be expensive (API calls to two external services + compute). An LRU TTL cache avoids redundant recomputation for recent queries.

## 2. Architecture

```python
class CorrelationCache:
    def __init__(self, maxsize=128, ttl=300):
        self._impact_cache = TTLCache(maxsize, ttl)
        self._correlation_cache = TTLCache(maxsize, ttl)
        self._drawdown_cache = TTLCache(maxsize, ttl)
```

Three separate caches for impact, correlation, and drawdown data. Each TTL cache evicts entries after `ttl` seconds.

## 3. Key design

Cache keys are tuples of `(symbol.upper(), from_ts, to_ts)`. All three caches share the same key structure.

## 4. Invalidation

| Method | Scope |
|--------|-------|
| `invalidate()` | Clear all caches |
| `invalidate(symbol)` | Clear only entries for the given symbol |

Invalidation is called automatically after `compute_and_store()` to ensure fresh data on next query.

## 5. Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `VINU_CORRELATION_CACHE_MAXSIZE` | 128 | Max cached entries per type |
| `VINU_CORRELATION_CACHE_TTL_SEC` | 300 | Entry TTL in seconds |
