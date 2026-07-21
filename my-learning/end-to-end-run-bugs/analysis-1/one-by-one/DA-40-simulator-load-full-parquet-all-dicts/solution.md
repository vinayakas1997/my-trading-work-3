# DA-40 🟡 Simulator Loads Full Parquet, Converts All to Dicts

**Component:** `vinu-simulator`
**Files Changed:** *(pending)*

## Problem

`get_result()` loads the full equity parquet and full trades parquet, converts ALL rows to dict lists. For a 5-year daily backtest, that's ~1260 equity points. Most callers only need latest value or a downsampled chart.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
