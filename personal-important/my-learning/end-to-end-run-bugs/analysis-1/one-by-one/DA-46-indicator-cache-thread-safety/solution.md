# DA-46 🟡 IndicatorCache Not Thread-Safe

**Component:** `vinu-stock-price`
**Files Changed:** *(pending)*

## Problem

`IndicatorCache` uses `OrderedDict` with no locking. Under concurrent requests (uvicorn workers), `get()`/`set()` mutations can corrupt the data structure.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
