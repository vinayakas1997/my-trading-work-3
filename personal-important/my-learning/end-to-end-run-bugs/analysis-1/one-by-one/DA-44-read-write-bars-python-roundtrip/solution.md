# DA-44 🟡 `read_bars`/`write_bars` Full Python Round-Trip

**Component:** `vinu-stock-price`
**Files Changed:** `vinu_stock/storage/parquet.py`, `vinu_stock/backfill/year_job.py`, `tests/test_parquet_io.py`, `tests/test_api.py`

## Problem

The merge path in `write_bars(merge=True)` did:
```
Parquet → pq.read_table() → .to_pylist() → BarRecord.from_dict() × N
→ combine with new list[BarRecord]
→ _dedupe_bars() → _bars_to_table() → .to_dict() × N → pa.array() → pq.write_table()
```

That's **two full Arrow↔Python round-trips** per merge. For 175k rows/year of backfill, this creates and discards ~350k frozen `BarRecord` dataclass instances.

## Root Cause

`_read_existing()` converted the PyArrow table to `list[BarRecord]`, then `_dedupe_bars()` worked on BarRecord objects, and `_bars_to_table()` converted them back. The deduplication only needs `(symbol, provider, bar_ts)` — three columns — not the full object construction.

## Solution

Replaced the BarRecord round-trip with direct PyArrow table deduplication:

- **Replaced `_dedupe_bars()` → `_dedupe_table()`** — extracts only the 3 key columns via `.to_pylist()`, tracks last-seen index, `table.take()` + `sort_by("bar_ts")`. Zero BarRecord objects created.

- **`_read_existing()` now returns `pa.Table`** — no conversion to dicts or BarRecord.

- **`write_bars()` now takes `pa.Table`** instead of `list[BarRecord]` — merge happens at table level via `pa.concat_tables()` + `_dedupe_table()`.

- **`read_bars()` now returns `pa.Table`** — internal callers (orchestrator, consolidate_live_shards) work directly with tables. `len()` and truthiness work identically on `pa.Table` via `__len__`.

- **`_bars_to_table()` renamed to `bars_to_table()`** (public) — still needed for the boundary where providers return `list[BarRecord]` (`year_job.py`, tests).

- **`consolidate_live_shards()`** simplified — reads table, writes directly (no merge needed, already deduped by `read_bars`).

## Verification

1. `ast.parse()` on `parquet.py` passes
2. Module import succeeds
3. `test_parquet_io.py::test_write_and_read_dedupe` passes — writes, appends, reads back, verifies dedup and correct close price (1.6, not 1.5)

## Performance Impact

- **Before:** 2 full Arrow↔Python↔Dataclass↔Python↔Arrow round-trips per merge
- **After:** 1 Python→Arrow conversion (new bars only, via `bars_to_table()`) + 1 Arrow-level filter + concat + take/sort
- Estimated improvement: ~50-70% faster for merge path, ~40% less memory (no intermediate BarRecord objects)
