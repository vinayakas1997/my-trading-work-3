# FP-5 🟠 No Retry Logic Anywhere in Pipeline

**Component:** `run_pipeline.py`
**Files Changed:** `run_pipeline.py`

## Problem

Every HTTP call in the pipeline runs exactly once. `_req()` raises on failure with no retry. `_poll_job()` does the same. Any transient HTTP 50x, connection reset, or timeout aborts the entire pipeline — losing all progress (potentially 90+ seconds of work).

## Root Cause

The pipeline had two patterns for HTTP calls, both without retry:

1. **`_req(method, url, **kwargs)`** — The centralized HTTP helper wrapped `requests.request()` + `raise_for_status()` but had zero retry logic.
2. **Raw `requests.post/get` calls** in step functions (`step_stock_price`, `step_news`, `step_initial_analysis`, `step_strategy`) used bare `requests.post/get` + `.raise_for_status()` with no retry.
3. **`_poll_job()`** — Polled job status in a loop but a single transient HTTP 500 on any poll request would abort the entire wait.

## What Was Changed

### 1. Added `_retry(fn, retries=3, base_delay=1.0)` helper (line 178)

A generic retry wrapper that catches `ConnectionError`, `Timeout`, and HTTP 5xx errors with exponential backoff (`delay = base_delay * 2^attempt`). Does NOT retry HTTP 4xx errors (client errors are non-transient). Logs each retry attempt with the `⟳` marker.

### 2. Modified `_req()` to use `_retry()` (line 227)

Wrapped `requests.request()` inside `_req()` with `_retry()`. All callers of `_req` (features, simulator, research) now automatically get retry.

### 3. Converted all raw requests calls to `_req()`

| Function | Before | After |
|----------|--------|-------|
| `step_stock_price:291` | `requests.post(...).raise_for_status()` | `_req("POST", ...)` |
| `step_stock_price:296` | `requests.post(...).raise_for_status()` | `_req("POST", ...)` |
| `step_stock_price:300` | `requests.post(...).raise_for_status()` | `_req("POST", ...)` |
| `step_news:314` | `requests.post(...).raise_for_status()` | `_req("POST", ...)` |
| `step_news:319` | `requests.get(...).raise_for_status()` | `_req("GET", ...)` |
| `step_news:331` | `requests.post(...)` (manual status check) | `_req("POST", ...)` + try/except |
| `step_initial_analysis:358` | `requests.post(...).raise_for_status()` | `_req("POST", ...)` |
| `step_strategy:365` | `requests.get(...).raise_for_status()` | `_req("GET", ...)` |
| `step_strategy:371` | `requests.post(...).raise_for_status()` | `_req("POST", ...)` |

### 4. Modified `_poll_job()` to use retry per poll request (line 207)

Wrapped the inner `requests.get()` with `_retry(lambda: requests.get(...))` so that a transient failure during one poll cycle doesn't abort the entire job wait.

### 5. News analyze error handling (line 330-334)

The per-article news analysis loop now wraps each call in try/except so one transient failure doesn't abort all remaining articles.

## Verification

1. Python syntax check: `python -c "import ast; ast.parse(open('run_pipeline.py').read()); print('OK')"` — passes.
2. Run pipeline with all services up: `python run_pipeline.py --ticker AAPL --from-date 2024-01-01 --to-date 2024-06-01` — should complete all steps.
3. Test transient failure: temporarily kill one service mid-run, verify `⟳ retry 1/3 after 1.0s: ...` logs appear in output, verify pipeline recovers after service comes back.
4. Test non-retriable error: point at a wrong port, verify 4xx/ConnectionRefused is logged once and fails immediately (no retry loop).
