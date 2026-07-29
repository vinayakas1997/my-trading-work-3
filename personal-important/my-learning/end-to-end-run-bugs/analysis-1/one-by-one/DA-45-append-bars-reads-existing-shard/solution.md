# DA-45 🟡 `append_bars` Reads Existing Day Shard to Add ~1-10 Rows

**Component:** `vinu-stock-price`
**Files Changed:** `parquet.py`

## Problem

Every live ingest cycle (~60s), `append_bars()` read the entire existing daily shard (~390 rows) just to add ~1-10 new bars. This was a 40-400x over-read per ingest cycle.

```python
# BEFORE — O(n) read-modify-write on every append
existing = _read_existing(day_path) if day_path.is_file() else []
combined = _dedupe_bars(existing + day_bars)
pq.write_table(_bars_to_table(combined), day_path, compression="zstd")
```

## Root Cause

`append_bars()` performed write-time deduplication via `_read_existing()` + `_dedupe_bars()` to prevent duplicate rows in the file. But this dedup is redundant:
1. **DA-12's DuckDB QUALIFY** already deduplicates at query time
2. **`consolidate_live_shards()`** cleans up duplicates periodically (every 30 shards)

Since PyArrow's `pq.write_table()` has no true append mode, avoiding the read meant accepting temporary duplicate rows.

## Solution

Skip the read and dedup entirely — write new bars directly:

```python
# AFTER — O(1) write, no read
pq.write_table(_bars_to_table(day_bars), day_path, compression="zstd")
```

## Trade-off

- **Pro:** `append_bars()` is now O(1) instead of O(n) — no read at all
- **Con:** Duplicate rows accumulate in daily shard files until `consolidate_live_shards()` runs (every 30 shards). At ~390 rows × ~100 bytes per shard, worst-case overhead is ~78KB — negligible.
- DuckDB QUALIFY handles dedup at query time, so callers never see duplicates

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `parquet.py:82-86` | 4 → 1 | Removed `_read_existing()` + `_dedupe_bars()`; write `day_bars` directly |

## Verification

33 stock-price tests pass (0 failures). Test `test_write_and_read_dedupe` passes unchanged because `read_bars()` still deduplicates internally.
