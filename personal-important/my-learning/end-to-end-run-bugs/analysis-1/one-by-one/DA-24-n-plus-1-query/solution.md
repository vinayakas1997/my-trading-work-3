# DA-24 🟡 N+1 Query in `get_news_for_watchlist`

**Component:** `vinu-news`
**Files Changed:** *(pending)*

## Problem

`get_news_for_watchlist()` iterates over each ticker and calls `get_news_for_ticker()` individually. For 50 tickers, that's 50 separate SQL queries.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
