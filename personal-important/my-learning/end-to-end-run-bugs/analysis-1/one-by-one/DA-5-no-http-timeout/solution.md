# DA-5 🟠 HTTP Calls Have No Timeout in vinu-initial-analysis

**Component:** `vinu-initial-analysis`
**Files Changed:** `net.py` — added default timeout Kwargs.setdefault

## Problem

`net.request()` passed `**kwargs` directly to `requests.request()` without injecting a default timeout. NewsClient and PriceClient never passed `timeout`, so all 3 outgoing HTTP calls could block indefinitely if downstream services hung.

## Root Cause

No default timeout in the central HTTP helper. The `requests` library default is no timeout.

## Solution

Added `kwargs.setdefault("timeout", (5, 30))` to `net.request()` — connect timeout of 5 seconds, read timeout of 30 seconds. A single change fixes all 3 affected call sites.

## Verification

All 60 tests pass (2 skipped).
