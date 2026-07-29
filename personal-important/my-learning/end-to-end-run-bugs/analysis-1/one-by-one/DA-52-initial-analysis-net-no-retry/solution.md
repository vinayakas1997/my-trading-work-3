# DA-52 🟠 vinu-initial-analysis net.request() has no transient retry

**Component:** `vinu-initial-analysis`
**Files Changed:** `vinu-initial-analysis/net.py`

## Problem

`net.request()` is the single HTTP choke point for all callers (price_client, news_client). It had no retry for transient errors — only a Docker loopback fallback for ConnectionRefused. Any timeout, HTTP 429, or 503 killed the request immediately, and the runners silently degraded to empty results.

## Root Cause

The function was a thin wrapper around `requests.request()` + Docker fallback. Transient error handling was never added because the initial-analysis component was built for synchronous local execution where failures were assumed to be permanent.

## Solution

Replaced the single-try body with a retry loop that:

1. **Exponential backoff** — 3 attempts (`delay = 1.0 * 1.5^attempt`) on transient errors
2. **Retryable errors** — `requests.Timeout`, `requests.ConnectionError`, HTTP 429/500/502/503/504
3. **Docker fallback integrated** — on first attempt, if ConnectionRefused on localhost, switches URL to `host.docker.internal` and retries (preserves existing behavior)
4. **Non-retryable errors** — HTTP 4xx propagate immediately via `raise_for_status()`
5. **After exhaustion** — last exception is re-raised (same behavior as current code)

### Files changed

| File | Change |
|------|--------|
| `vinu-initial-analysis/net.py` | Added retry loop with backoff, integrated Docker fallback, added `_REATTEMPTS`/`_BACKOFF` constants |

### Verification

1. `python -c "import ast; ast.parse(open('vinu-initial-analysis/net.py').read()); print('OK')"`
2. `from vinu_initial_analysis.net import request` — resolves correctly
