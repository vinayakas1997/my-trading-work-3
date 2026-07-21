# DA-39 🟡 Initial Analysis Reads Full Parquet, Filters in Python

**Component:** `vinu-initial-analysis`
**Files Changed:** *(pending)*

## Problem

`get_impact()` reads the entire `news_price_causality` parquet file for a symbol, then filters in Python — using only 5-20% of rows. `get_correlation()` reads all rows but uses only the last `type == "correlation"` record.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
