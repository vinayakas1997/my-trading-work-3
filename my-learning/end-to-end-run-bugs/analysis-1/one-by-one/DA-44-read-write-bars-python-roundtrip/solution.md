# DA-44 🟡 `read_bars`/`write_bars` Full Python Round-Trip

**Component:** `vinu-stock-price`
**Files Changed:** *(pending)*

## Problem

`read_bars()` and `write_bars(merge=True)` convert Parquet data through Arrow→dict→dataclass unnecessarily. Backfill consolidation creates ~175k `BarRecord` objects per year.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
