# DA-46 🟡 IndicatorCache Not Thread-Safe

**Component:** `vinu-stock-price`
**Files Changed:** `cache.py`

## Problem

`IndicatorCache` docstring claimed "Thread-safe LRU cache" but used `OrderedDict` mutations (`.get()`, `.move_to_end()`, `.popitem()`, `.clear()`, `del`) without any locking. Under concurrent API requests, this could cause `RuntimeError: dictionary changed size during iteration` or silent data corruption.

## Root Cause

The `__init__` method never created a `threading.Lock`. All `get()`, `set()`, and `invalidate()` methods directly mutated the `OrderedDict` without synchronization.

## Fix

Added `self._lock = threading.Lock()` and wrapped all `OrderedDict` operations in `with self._lock:` blocks:

- `get()` — `_cache.get()`, `del _cache[key]`, `_cache.move_to_end()` under lock
- `set()` — `_cache.popitem()`, `_cache[key] = ...` under lock
- `invalidate()` — `_cache.clear()`, `del _cache[k]` under lock

Lock is released before returning data from `get()` to minimize contention.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `cache.py:5,31,44-52,66-69,72-79` | 5 added | `import threading` + `self._lock` + `with self._lock:` on all 3 methods |

## Verification

33 stock-price tests pass (0 failures). The cache is exercised by `test_indicators.py`.
