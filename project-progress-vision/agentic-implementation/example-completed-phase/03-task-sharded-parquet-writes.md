# Task 3: Sharded Parquet Writes in ParquetStore

**Status:** DONE

## Purpose

Add `write_shard()`, `read_shard()`, and `consolidate()` methods to `ParquetStore` so it supports the hot/cold data lifecycle that stock-price uses (daily live shards consolidated into yearly archive files).

## Approach

Follow stock-price's existing file layout convention (`{data_root}/prices/1m/{SYMBOL}/archive|live/...`). Each shard is a separate parquet file; `consolidate()` reads all shards in a glob pattern, deduplicates on the configured key, and writes a single consolidated file.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-lib/parquet.py` | 134-178 | Added `write_shard(rel_path, records, dedup_on)` |
| `vinu-lib/parquet.py` | 180-210 | Added `read_shard(rel_path_glob)` |
| `vinu-lib/parquet.py` | 212-250 | Added `consolidate(archive_pattern, output_path, dedup_on)` |
| `vinu-lib/tests/test_parquet.py` | 60-120 | Added `TestShardedWrites` and `TestConsolidation` test classes |

## Verification

- [x] `write_shard` creates file at expected path with correct schema
- [x] `read_shard` with glob returns union of matching shards
- [x] `consolidate` merges shards and deduplicates correctly
- [x] Existing non-sharded append/read path unchanged
