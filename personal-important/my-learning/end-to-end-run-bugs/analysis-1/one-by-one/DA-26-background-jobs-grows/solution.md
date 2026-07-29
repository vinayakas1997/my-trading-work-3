# DA-26 🟡 `_background_jobs` Dict Grows Unbounded

**Component:** `vinu-stock-price`
**Files Changed:** *(pending)*

## Problem

Every `POST /backfill/trigger` and `POST /ingest/trigger` adds an entry to `_background_jobs` that is **never removed**. Memory leak over time.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
