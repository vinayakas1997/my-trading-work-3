# DA-25 🟡 On-Demand + Auto-Analysis Can Race for Same Article

**Component:** `vinu-news`
**Files Changed:** `analyze.py`

## Problem

Two code paths both call `analyze_article()` concurrently for the same URL:
1. **On-demand** — `POST /news/analyze` → `service.analyze_article()` → `analyze_article(repo, url)`
2. **Auto-analysis** — `AutoAnalysisWorker._worker_loop()` → `analyze_article(repo, link)`

Both check the cache, and if both pass the check before either saves, **both make an LLM call for the same article** — wasting one. With conservative rate limits (`VINU_LLM_RATE_LIMIT=5`), this is especially costly.

## Root Cause

`analyze_article()` had no coordination. Cache check → LLM call → save is not atomic. Two threads can both pass the cache check simultaneously.

## Fix

Added a module-level `_IN_PROGRESS` set (protected by `_IN_PROGRESS_LOCK`) and double-check locking in `analyze_article()`:

1. First cache check (fast path — no lock)
2. Under lock: if URL is already being analyzed by another thread, double-check cache
   - Cache hit now: return cached result
   - Still no cache: return skip response (`"analysis": None`)
   - If not in progress: add URL to set, release lock
3. Do LLM call + save normally
4. `finally`: remove URL from `_IN_PROGRESS` (ensures cleanup on exception or success)

## Behavioral Change

On a concurrent duplicate request, returns `{"url": url, "cached": False, "analysis": None}` instead of making a second LLM call. This saves LLM calls at the cost of a null response during the race window.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `analyze.py:5` | Added | `import threading` |
| `analyze.py:14-15` | Added | `_IN_PROGRESS` set + `_IN_PROGRESS_LOCK` |
| `analyze.py:43-64` | Changed | Double-check locking + `try/finally` cleanup around LLM call |

## Verification

50 news tests pass (0 failures). `test_llm_analyze.py` exercises the analyze path directly.
