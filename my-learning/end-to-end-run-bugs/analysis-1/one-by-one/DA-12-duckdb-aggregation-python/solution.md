# DA-12 🟠 DuckDB Aggregation Done in Python Instead of SQL

**Component:** `vinu-stock-price`
**Files Changed:** *(pending)*

## Problem

When requesting 1d candles, the engine reads ALL 1m bars from DuckDB into Pandas, converts to `list[dict]`, then iterates in Python to bucket-aggregate by day.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
