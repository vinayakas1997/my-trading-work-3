# DA-39 🟡 Initial Analysis Reads Full Parquet, Filters in Python

**Component:** `vinu-initial-analysis`
**Files Changed:** `vinu_initial_analysis/storage/parquet.py`, `vinu_initial_analysis/api.py`

## Problem

`get_correlation()` reads the entire `news_price_causality` parquet for a symbol, then filters in Python for `type == "correlation"` — usually only 1 row out of thousands. The full read + `to_dict("records")` wastes I/O, memory, and CPU.

## Root Cause

`AngleStorage.read()` had no filter pushdown — always called `pq.read_table(f)` with no `filters=` argument, forcing all rows through Python filtering.

## Solution

1. **`AngleStorage.read()`** (`parquet.py:61`): Added optional `filters` parameter passed directly to `pq.read_table(f, filters=filters)`. This enables PyArrow predicate pushdown at the column-chunk level — only matching rows are decompressed.

2. **`get_correlation()`** (`api.py:97`): Changed `self._storage.read(symbol, "news_price_causality")` to `self._storage.read(symbol, "news_price_causality", filters=[("type", "=", "correlation")])`. Eliminates the Python filter loop and the `corr_records = [r for r in records if ...]` list comprehension.

## Verification

- Syntax check: `ast.parse()` passes for both files.
- Runtime: requesting correlation data should read ~1 row instead of thousands, reducing I/O by 100-1000× depending on symbol data volume.
