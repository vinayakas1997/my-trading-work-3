# DA-14 🟡 Parquet Files Accumulate Unbounded in vinu-initial-analysis

**Component:** `vinu-initial-analysis`
**Files Changed:** *(pending)*

## Problem

Every `run()` creates a **new parquet file** per angle per symbol. There is no compaction, no retention policy, no merging. After 100 runs, 100 files are read per query.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
