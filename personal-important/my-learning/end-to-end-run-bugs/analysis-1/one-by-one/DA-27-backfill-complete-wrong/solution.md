# DA-27 🟠 Backfill Sets "complete" Even When Some Years Failed

**Component:** `vinu-stock-price`
**Files Changed:** `orchestrator.py`, `store.py`, `year_job.py`

## Problems Found (3 related issues)

### Issue 1: Unconditional "complete" (the critical bug)
`orchestrator.py:135` set `backfill_status="complete"` after the per-year loop regardless of `summary.years_failed`. Failed years were permanently buried — next backfill cycle skips the symbol.

### Issue 2: Retry re-downloads ALL years (wasted work)
When a `"partial"` symbol was retried, `_backfill_symbol` looped from `start_year` to `end_year` re-downloading already-completed years. The `backfill_jobs` table already tracks per-year status (`queued|done|failed`) but it was never checked.

### Issue 3: `year_job.py` sets `backfill_status="partial"` on every successful year
This was redundant — the orchestrator already manages the symbol-level status. Setting it on individual year success was misleading.

## Fixes

### 1. Conditional final status (`orchestrator.py:135`)
```python
if summary.years_failed > 0:
    catalog.upsert_symbol(sym, backfill_status="partial")  # retry next cycle
else:
    catalog.upsert_symbol(sym, backfill_status="complete")
```

### 2. Skip already-done years on retry (`orchestrator.py:110-133`)
Added check at the top of each year iteration: if `get_job_status()` returns `"done"`, skip it. Only `failed`/`queued`/new years are processed.

### 3. New `get_job_status()` method (`store.py:189-195`)
Queries the `backfill_jobs` table for a specific `(symbol, year)` pair. Used by the orchestrator to skip done years.

### 4. Remove redundant status (`year_job.py:51`)
Removed `backfill_status="partial"` from `year_job.py` — orchestrator already sets it at the start of `_backfill_symbol`.

## Files Changed

| File | Change |
|------|--------|
| `catalog/store.py:189-195` | Added `get_job_status()` method |
| `backfill/orchestrator.py:110-134` | Skip done years; conditional final status |
| `backfill/year_job.py:47-54` | Removed redundant `backfill_status="partial"` |

## Verification

33 tests pass. All modules import cleanly.
