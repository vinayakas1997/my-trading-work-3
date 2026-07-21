# DA-4 🟠 `--incremental` Is Dead Code in vinu-initial-analysis

**Component:** `vinu-initial-analysis`
**Files Changed:**
- `cli.py` — removed `--incremental` flag, removed `incremental` param from `_compute_batch()`, removed log msg
- `api.py` — removed `incremental` param from `compute_and_store()`
- `service.py` — removed `incremental` param from `compute()`, removed log msg

## Problem

The `--incremental` flag existed but was never acted upon. It was parsed, logged, and threaded through `_compute_batch()` → `api.compute_and_store()` → `service.compute()`, but never forwarded to `runner.run()`. Every compute was always a full recompute.

## Root Cause

Legacy artifact from the old `vinu-correlation` system. When refactored into `vinu-initial-analysis` with the angle-runner architecture, the incremental logic was never carried over. The flag and its parameters became vestigial.

## Solution

Removed `--incremental` from CLI, removed the `incremental` parameter from `_compute_batch()`, `CorrelationAPI.compute_and_store()`, and `InitialAnalysisService.compute()`.

## Verification

- `grep -r incremental vinu-initial-analysis/` returns nothing
- All 60 tests pass (2 skipped)
