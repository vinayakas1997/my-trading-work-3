# DA-14 🟡 Parquet Files Accumulate Unbounded

**Component:** `vinu-initial-analysis`
**Files Changed:** `storage/parquet.py`, `tests/test_parquet.py` (new)

## Problem

Every `AngleStorage.write()` call creates a new `{uuid}.parquet` file under `data/analysis/{symbol}/{angle_name}/`. There was zero cleanup — files accumulate without bound, growing both disk usage and read latency (since `read()` concatenates ALL files).

## Root Cause

`write()` generated a new file on every call with `uuid4().hex[:12]` as the filename. No `delete`, `prune`, `rotate`, or `retire` mechanism existed anywhere in the class or its callers.

## Solution

1. Added `_cleanup(symbol, angle_name, max_runs)` method — sorts files by `st_mtime`, deletes oldest when count exceeds `max_runs`
2. Added `cleanup_max_runs: int = 10` parameter to `write()` — called automatically after each write
3. Setting `cleanup_max_runs=0` disables cleanup (opt-out for special cases)
- No changes to any caller — existing code continues working

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `storage/parquet.py:28-59` | Changed | Added `cleanup_max_runs=10` param to `write()`; calls `self._cleanup()` after writing |
| `storage/parquet.py:112-121` | Added | New `_cleanup()` method: sorts files by mtime, deletes oldest beyond max_runs |
| `tests/test_parquet.py` | New | 7 tests covering: keeps max runs, removes oldest, disabled with zero, read after cleanup, read_latest, list_angles |

## Verification

67 tests pass (0 failures). All existing tests continue to work — cleanup is opt-out with a sensible default.
