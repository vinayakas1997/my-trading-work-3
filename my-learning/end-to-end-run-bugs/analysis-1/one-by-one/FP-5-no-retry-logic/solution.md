# FP-5 🟠 No Retry Logic Anywhere in Pipeline

**Component:** `run_pipeline.py`
**Files Changed:** *(pending)*

## Problem

Every step runs exactly once. `_req()` calls `raise_for_status()` with no retry. `_poll_job()` does the same. Any transient HTTP 50x, connection reset, or timeout aborts the entire pipeline.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
