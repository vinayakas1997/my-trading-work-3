# Chapter 18 — Parquet compaction

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/storage/backend.py` (compact) |
| **Status** | DRAFT |
| **Prerequisites** | ch17 |

## 1. Problem

Repeated appends create Parquet files with many row groups, degrading read performance. Compaction rewrites the full table as a single optimized Parquet file.

## 2. Trigger

Compaction is invoked explicitly via:

```bash
vinu-correlation-compact AAPL --year 2026
vinu-correlation-compact --all
```

Or triggered automatically when the number of row groups exceeds `VINU_CORRELATION_COMPACT_THRESHOLD` (default 50).

## 3. Logic

```python
def compact(self, symbol, year, force=False):
    for path_fn in [impact_path, baseline_path, correlation_path]:
        path = path_fn(self._data_root, symbol, year)
        existing = self._read_existing(path)
        if existing is not None:
            pq.write_table(existing, path)  # single consolidated write
```

## 4. Tests

| Test file | Asserts |
|-----------|---------|
| (covered by `test_incremental.py`) | |
