# DA-53 🟡 vinu-news net.request() has no transient retry

**Component:** `vinu-news`
**Files Changed:** `vinu-news/net.py`

## Problem

`vinu-news/net.py` had the same pattern as the initial-analysis version — Docker loopback fallback only, zero transient retry. Two callers (`integrations/stock_price.py`, `service.py` health endpoint) would fail immediately on transient HTTP errors.

## Root Cause

Same as DA-52 — the function was built for Docker networking scenarios only, not for general HTTP resilience.

## Solution

Replaced the single-try body with a retry loop identical to DA-52:

1. **Exponential backoff** — 3 attempts (`delay = 1.0 * 1.5^attempt`) on transient errors
2. **Retryable errors** — `requests.Timeout`, `requests.ConnectionError`, HTTP 429/500/502/503/504
3. **Docker fallback integrated** — on first attempt, ConnectionRefused on localhost switches URL to `host.docker.internal`
4. **Non-retryable errors** — HTTP 4xx propagate immediately

### Files changed

| File | Change |
|------|--------|
| `vinu-news/net.py` | Added retry loop with backoff, integrated Docker fallback |

### Verification

1. `python -c "import ast; ast.parse(open('vinu-news/net.py').read()); print('OK')"`
2. `from vinu_news.net import request` — resolves
