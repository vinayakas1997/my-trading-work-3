# DA-55 🟡 vinu-tools features route has no retry

**Component:** `vinu-tools`
**Files Changed:** *(pending)*

## Problem

`vinu_tools/server/routes_features.py:71` makes an `httpx.AsyncClient().get()` upstream call with no retry. If the upstream (stock-api) is briefly down, `raise_for_status()` triggers and the endpoint returns HTTP 502 to the caller — even though a retry 1-2 seconds later would succeed.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
