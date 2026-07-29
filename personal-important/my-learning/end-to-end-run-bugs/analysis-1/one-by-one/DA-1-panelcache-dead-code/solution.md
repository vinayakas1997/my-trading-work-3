# DA-1 🔴 PanelCache Is Dead Code in vinu-tools

**Component:** `vinu-tools`
**Files Changed:** `vinu_tools/compute/data_cache.py` (deleted)

## Problem

`PanelCache` is a fully implemented in-memory cache for OHLCV panel data (120 lines with TTL and LRU eviction), but nobody imports or calls it anywhere in the codebase. It is entirely dead code.

## Root Cause

The cache was presumably built as a future optimization for factor computation, but the `compute_factor()` pipeline in `bridge.py` never wired it in. No module imports `get_cache()` or `PanelCache` from `data_cache.py`.

## Solution

Deleted `vinu_tools/compute/data_cache.py` (120 lines removed). Clean delete — no imports to clean up.

## Verification

- `grep -r data_cache vinu-components/` returns no results
- Syntax check passes across the entire vinu-tools codebase
