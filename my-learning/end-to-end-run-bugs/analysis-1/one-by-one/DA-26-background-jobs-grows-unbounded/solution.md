# DA-26 🟡 `_background_jobs` Dict Grows Unbounded

**Component:** `vinu-stock-price`
**Files Changed:** `routes_config.py`

## Problem

`_background_jobs` dict stores job status for backfill and ingest operations. Jobs are added when triggered (2 new job types) and updated when done/failed (4 status updates), but **never cleaned up**. The dict grows unbounded — a memory leak proportional to the number of trigger requests.

## Root Cause

No cleanup logic existed. Every backfill or ingest trigger adds a new entry to `_background_jobs` via `_background_jobs[job_id] = ...` (lines 101, 110, 125, 154, 161, 174 of the original). Old completed/failed jobs accumulate forever.

## Fix

Added a `_JOBS_MAX = 50` constant and a `_cleanup_old_jobs()` helper that removes the single oldest entry (via `next(iter(_background_jobs))`) in a `while` loop until the dict is at or under the limit. Called at all 6 assignment sites under the existing `_jobs_lock`.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `routes_config.py:27,30-34` | 5 added | `_JOBS_MAX = 50` constant + `_cleanup_old_jobs()` helper |
| `routes_config.py:102,122,131,155,170,179` | 6 added | `_cleanup_old_jobs()` call after each `_background_jobs` assignment |

## Verification

33 stock-price tests pass (0 failures). Existing `test_catalog.py::test_catalog_upsert_and_jobs` exercises trigger/status flow.
