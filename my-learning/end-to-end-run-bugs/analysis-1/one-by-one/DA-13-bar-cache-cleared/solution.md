# DA-13 🟡 `_bar_cache` Cleared at Start of Every `run()` Call

**Component:** `vinu-initial-analysis`
**Files Changed:** *(pending)*

## Problem

The `_bar_cache` dict caches bars by `(symbol, time_format)` within a single `run()` call. But it's **cleared at the start of every `run()`** (line 89: `self._bar_cache.clear()`). This means every call to `run(symbol)` re-fetches bars from the network.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
