# Fixes Applied to vinu-components

## 1. Alpaca Stock Provider — Default Feed

**File:** `vinu-stock-price/vinu_stock/providers/alpaca.py`

**Problem:** The provider tried SIP feed first, got a 403 error, then retried with IEX. This added ~500ms overhead per request.

**Fix:** Changed default `feed` parameter from `sip` to `iex`. SIP access requires a higher-tier Alpaca plan; the basic/Broker API plan only has IEX access.

**Changed line:**
```python
# Before:
async def get_trade(symbol, feed="sip"):
# After:
async def get_trade(symbol, feed="iex"):
```

**Impact:** Removes the SIP→403→IEX retry cycle. Each request now goes directly to IEX.

---

## 2. Alpaca News Provider — Error Logging

**File:** `vinu-news/vinu_news/providers/alpaca.py`

**Problem:** When the Alpaca news API returned an error (non-200 status), the code silently broke out of the pagination loop without logging the HTTP status code, response body, or the date range and page number that caused the failure. This made debugging impossible.

**Fix:** Added detailed error logging before the `break`:
- HTTP status code
- Response body (first 500 chars)
- Date range being queried (`from_date`, `to_date`)
- Current page number

**Impact:** Any future Alpaca news API failures will now log sufficient context to diagnose the issue immediately.

---

## 3. MIN_BACKFILL_YEAR — Changed to 2022

**File:** `vinu-stock-price/vinu_stock/backfill/orchestrator.py`

**Problem:** `MIN_BACKFILL_YEAR` was set to 2023, so backfill only retrieved 2023–2025 data. The strategy requires data starting from 2022-01-01.

**Fix:** Changed `MIN_BACKFILL_YEAR` from `2023` to `2022`.

**Impact:** Backfill now retrieves 4 years of data (2022, 2023, 2024, 2025) instead of 3.

---

## 4. `earliest_available()` — Fixed Probe Method

**File:** `vinu-stock-price/vinu_stock/providers/alpaca.py`

**Problem:** The function tried to probe the earliest available date by requesting 1-minute bars over a 365-day window, which failed on IEX feed (IEX doesn't provide 1m historical data for extended periods). This caused the discovery of the earliest bar to fail.

**Fix:** Changed to use daily IEX feed (`interval=1Day`) for the probe instead of 1-minute bars. Daily bars are available on IEX for the full historical range.

**Impact:** `earliest_available()` now correctly returns 2022-01-03 instead of throwing an error.

---

## 5. Providers Configuration — Only Alpaca Enabled

**File:** `vinu-stock-price/vinu_stock/providers/config/providers.yaml`

**Problem:** Multiple providers were enabled, causing fallback chains to try Polygon, Yahoo, etc. when Alpaca was the only configured provider with API keys.

**Fix:** Set all provider roles to only Alpaca:
```yaml
providers:
  - id: alpaca
    enabled: true
    priority: 1
```

**Impact:** No unnecessary provider fallback attempts. All requests go directly to Alpaca.
