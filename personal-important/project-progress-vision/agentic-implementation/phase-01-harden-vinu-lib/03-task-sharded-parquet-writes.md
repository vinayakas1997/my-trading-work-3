# Task 3: Add Sharded Writes and Consolidation to ParquetStore

**Status:** DONE

## Purpose

Add `read_shard()` and `consolidate()` methods to `ParquetStore` so it supports the shard-based data lifecycle that stock-price uses (daily live shards consolidated into archive files). This lets downstream packages avoid hand-rolling their own shard read/merge/delete logic.

## Approach

- `read_shard(rel_glob: str, dedup_on=None)` — reads all parquet files matching a glob pattern under `data_root`, concatenates them, optionally deduplicates. Returns `None` if no files match.
- `consolidate(shard_glob, output_rel_path, dedup_on=None)` — reads all shards matching the glob, deduplicates, writes consolidated output, then deletes the individual shard files. Returns row count.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-components/vinu-infra/parquet.py` | 48-98 | Added `read_shard()`, `consolidate()` methods |
| `vinu-components/vinu-infra/tests/test_parquet.py` | 67-121 | Added `TestReadShard` and `TestConsolidation` tests |

## Verification

- [x] `read_shard` returns union of matching shard files
- [x] `read_shard` returns None for nonexistent glob
- [x] `read_shard` with dedup_on deduplicates correctly
- [x] `consolidate` merges shards into output file
- [x] `consolidate` deletes source shard files after consolidation
- [x] `consolidate` with dedup_on deduplicates across shards
- [x] `consolidate` returns 0 for empty glob (no crash)
