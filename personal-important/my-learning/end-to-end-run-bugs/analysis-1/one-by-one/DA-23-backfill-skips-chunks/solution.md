# DA-23 🟠 Backfill Skips Chunks on HTTP Error (Silent Data Gaps)

**Component:** `vinu-news`
**Files Changed:** `registry.py`, `service.py`, `test_ticker_news_provider.py`

## Problem

When all providers fail (timeout, DNS, HTTP 500), `fetch_for_ticker()` returned an empty `[]` — indistinguishable from "no articles in this time range." The backfill loop treated empty as "done" and advanced the chunk pointer. The ingestion path hardcoded `feeds_failed = 0`, reporting success even when all providers failed.

Three silent data loss scenarios:
1. **Backfill**: Failed chunks advance `backfilled_up_to_ts` — permanent gap
2. **Completion**: `mark_backfill_completed` ran even when chunks failed — never retried
3. **Ingestion**: `feeds_failed` always 0 for ticker_news — caller thinks it worked

## Root Cause

`fetch_for_ticker()` caught provider exceptions and used `continue` — no way for callers to distinguish empty (no articles) from empty (all providers failed).

## Solution

### 1. `registry.py` — Return error info
Changed return type from `list[dict]` to `tuple[list[dict], list[str]]` — `(articles, failed_provider_ids)`. Callers can now check if `errors` is non-empty to detect provider failures.

### 2. `service.py` — Backfill retry + conditional completion
- Re-fetch failed chunks once before giving up
- Persist `error_message` via `update_backfill_progress(..., error_message=...)` for permanent failures
- Only call `mark_backfill_completed` if no chunks had permanent errors; otherwise log the gap

### 3. `service.py` — Ingestion error tracking
- Track `feeds_failed` from actual provider errors instead of hardcoding `0`
- Log warnings per ticker with provider errors

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `providers/registry.py:42-68` | ~20 | Return `(articles, errors)` tuple |
| `service.py:438-476` | ~35 | Backfill: unpack tuple, retry once, conditional completion |
| `service.py:525-531` | ~10 | Ingestion: unpack tuple, count feeds_failed |
| `test_ticker_news_provider.py:6-73` | ~40 | 2 tests: partial failure + all providers fail |

## Verification

`test_ticker_news_provider.py` — 2 tests pass (mock success + mock all-fail). Code imports cleanly.
