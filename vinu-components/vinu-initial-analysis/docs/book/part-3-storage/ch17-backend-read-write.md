# Chapter 17 — Backend read/write

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/storage/backend.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch15, ch16 |

## 1. Problem

The `CorrelationStorage` class provides the read/write interface for all three data types (impact events, baselines, correlation matrices) using Apache Parquet via PyArrow and DuckDB.

## 2. Read methods

| Method | Description |
|--------|-------------|
| `get_last_computed_ts(symbol)` | Scan Parquet files for max timestamp |
| `read_events(symbol, year)` | Read a single year of events |
| `read_events_range(symbol, from_ts, to_ts)` | Query events in a time range (DuckDB SQL over Parquet glob) |

## 3. Write methods

| Method | Description |
|--------|-------------|
| `append_events(symbol, events)` | Append + dedup by `(article_id, symbol)` |
| `append_baselines(symbol, baselines)` | Append baseline snapshots |
| `append_correlations(symbol, correlations)` | Append correlation matrices |

## 4. Dedup logic

On append, the existing table is read, concatenated with new data, deduplicated by `(article_id, symbol)` keeping the most recent `computed_at`, and written back.

```python
def _dedup_by_article_id(table):
    df = table.to_pandas()
    df = df.sort_values("computed_at", ascending=False)
             .drop_duplicates(subset=["article_id", "symbol"], keep="first")
    return pa.Table.from_pandas(df, schema=table.schema)
```

## 5. Range queries

`read_events_range` uses DuckDB SQL to glob-read all Parquet files in a symbol directory and filter by timestamp:
```sql
SELECT * FROM read_parquet('{glob_pattern}')
WHERE symbol = ? AND ts >= ? AND ts <= ?
```

## 6. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_incremental.py` | Append, dedup, range queries |
