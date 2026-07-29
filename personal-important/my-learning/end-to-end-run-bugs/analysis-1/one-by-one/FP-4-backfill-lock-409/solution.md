# FP-4 🟡 Backfill Lock Returns 409 Immediately

**Component:** `vinu-stock-price`, `run_pipeline.py`
**Files Changed:** `vinu-stock-price/vinu_stock/server/routes_config.py`, `run_pipeline.py`

## Problem

`routes_config.py` used `threading.Lock.acquire(blocking=False)` for the backfill and ingest locks. If the lock was held, the endpoint raised HTTP 409 immediately with no way for the client to recover. `run_pipeline.py` had no 409 handling — it would try to parse `job_id` from the 409 JSON response (which had no `summary.job_id`), get `None`, and silently skip polling. The pipeline would proceed with stale/missing data.

## Root Cause

Two issues:
1. **Server side:** 409 response did not include the running `job_id`, so the client couldn't recover by polling the existing job.
2. **Client side:** `run_pipeline.py` treated the 409 response the same as a 200 — tried to parse `job_id` from `summary`, got `None`, and silently continued without waiting for the running job to complete.

## Solution

### routes_config.py
1. Added `_get_running_job_id(job_type)` helper that scans `_background_jobs` for a running job of the given type.
2. When 409 is raised, the detail now includes the `job_id` of the running job: `"Backfill already running (job_id=abc123)"`. Same for ingest.

### run_pipeline.py
1. Added `import re`.
2. Replaced inline trigger/poll logic with a `_trigger_and_poll()` helper that:
   - On 200: parses `job_id` from `summary` and polls normally.
   - On 409: extracts `job_id` from the error detail via regex and polls the existing job.
   - On other errors: raises `RuntimeError`.

### Files changed

| File | Change |
|------|--------|
| `vinu-stock-price/vinu_stock/server/routes_config.py` | Added `_get_running_job_id()`, included `job_id` in 409 detail for both backfill and ingest |
| `run_pipeline.py` | Added `re` import, replaced trigger logic with `_trigger_and_poll()` helper that handles 409 gracefully |

### Verification

1. `python -c "import ast; ast.parse(open('routes_config.py').read()); print('OK')"` ✓
2. `python -c "import ast; ast.parse(open('run_pipeline.py').read()); print('OK')"` ✓
3. `from vinu_stock.server.routes_config import router` ✓
4. `import run_pipeline` ✓
