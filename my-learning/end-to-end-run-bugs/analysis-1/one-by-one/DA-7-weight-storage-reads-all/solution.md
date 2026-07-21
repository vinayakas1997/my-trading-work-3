# DA-7 🟠 Weight Storage Reads ALL Parquet Files Then Filters

**Component:** `vinu-strategy`
**Files Changed:** `weights.py` — `_collect_tables()` and `read_weights()`

## Problem

`read_weights()` called `_collect_tables()` which read every `.parquet` file under the strategy directory tree, concatenated all tables, converted to pandas, THEN filtered by symbol and date range. A query for a single symbol on a single date read ALL files across all years/months/symbols.

## Root Cause

No date-based directory pruning and no predicate pushdown in Parquet reads. The old `_collect_tables` accepted only `strategy_dir` and called `pq.read_table()` with no `filters` argument.

## Solution

Two-pronged approach:

1. **Directory pruning** — Skip year/month/day directories based on `from_ts`/`to_ts` before reading any file.
2. **PyArrow predicate pushdown** — Pass `filters=[("symbol", "==", ...), ("date", ">=", ...), ("date", "<=", ...)]` to `pq.read_table()` so only matching row groups are materialized.

`_collect_tables()` accepts `symbol`, `from_ts`, `to_ts` parameters and handles both pruning and filtering. `read_weights()` delegates entirely to the enhanced `_collect_tables()` and removes its redundant post-hoc filtering.

## Verification

All 63 existing tests pass (1 pre-existing failure in test_expression.py unrelated to this change).
