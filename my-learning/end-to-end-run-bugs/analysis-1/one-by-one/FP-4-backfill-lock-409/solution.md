# FP-4 🟡 Backfill Lock Returns 409 Immediately

**Component:** `vinu-stock-price`
**Files Changed:** *(pending)*

## Problem

The backfill lock uses `acquire(blocking=False)` — if a backfill is already running, the caller gets an immediate HTTP 409 with `"Backfill already running"`. The caller has no fallback (no queue, no join, no retry).

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
