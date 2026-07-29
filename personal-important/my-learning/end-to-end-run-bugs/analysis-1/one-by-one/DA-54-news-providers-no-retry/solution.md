# DA-54 🟡 vinu-news providers (yahoo/alpaca/rss) have no retry

**Component:** `vinu-news`
**Files Changed:** *(pending)*

## Problem

`vinu_news/providers/yahoo.py`, `alpaca.py`, and `rss/fetch/http_client.py` all make direct `requests.get()` calls with no retry wrapper. A transient 429 or 503 from the upstream provider silently loses articles for that ticker/cycle.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
