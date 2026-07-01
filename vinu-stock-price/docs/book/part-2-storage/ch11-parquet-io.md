# Chapter 11 — Parquet I/O

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | `vinu_stock/storage/parquet.py` |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Chapter 08, Chapter 09 |

## Learning objectives

- Use `write_bars`, `append_bars`, and `read_bars` correctly.
- Explain merge-and-dedupe behavior on repeated writes.
- Map PyArrow schema columns to `BarRecord` fields.

## 1. Problem this module solves

1m OHLCV must persist efficiently and reload for DuckDB queries. `parquet.py` converts `BarRecord` lists to **PyArrow tables**, writes **zstd-compressed** Parquet, and on merge **deduplicates** by `(symbol, provider, bar_ts)` so backfill reruns and live overlap do not duplicate rows.

## 2. Position in pipeline

```mermaid
flowchart LR
  A[BarRecord list] --> B[_bars_to_table]
  B --> C[merge existing?]
  C --> D[_dedupe_bars]
  D --> E[pq.write_table zstd]
  E --> F[.parquet file]
  F --> G[read_bars / DuckDB]
```

| Step | Input | Output |
|------|-------|--------|
| `write_bars(path, bars, merge=True)` | New bars + optional existing file | Full deduped file, returns row count |
| `append_bars(path, bars)` | New bars | Alias for `write_bars(..., merge=True)` |
| `read_bars(path)` | Path | `list[BarRecord]` |
| DuckDB | glob paths | SQL rows (query engine) |

## 3. File map

| File | Responsibility |
|------|----------------|
| `storage/parquet.py` | Core read/write/dedupe |
| `storage/models.py` | `BarRecord`, `to_dict`/`from_dict` |
| `storage/paths.py` | Target file paths |
| `backfill/year_job.py` | `parquet.write_bars` → archive |
| `live/ingest_cycle.py` | `parquet.append_bars` → live |
| `query/engine.py` | DuckDB `read_parquet` (bypasses `read_bars`) |

## 4. Data contracts

### Input

| Field | Type | Required | Example |
|-------|------|----------|---------|
| `path` | Path | yes | `.../archive/2024.parquet` |
| `bars` | list[BarRecord] | yes | Provider fetch result |
| `merge` | bool | no (default True) | Read existing before write |

### Output

| Field | Type | Example |
|-------|------|---------|
| Return value | int | Total rows after dedupe |
| Parquet columns | 11 fields | See `_BAR_FIELDS` |
| Compression | codec | `zstd` |

### Parquet schema (`_BAR_FIELDS`)

| Column | Arrow type |
|--------|------------|
| symbol | string |
| provider | string |
| bar_ts | int64 |
| open, high, low, close, volume, vwap, adj_factor | float64 |
| trades | int64 |

## 5. Logic (step by step)

1. **`_bars_to_table(bars)`** — empty list yields typed empty columns; else builds column arrays from `bar.to_dict()`.
2. **`write_bars(path, bars, merge=True)`**:
   - `path.parent.mkdir(parents=True, exist_ok=True)`.
   - If `merge` and file exists, `_read_existing(path)` prepends current rows.
   - `_dedupe_bars(combined)` — dict key `(symbol, provider, bar_ts)`, last wins, sort by `bar_ts`.
   - `pq.write_table(..., compression="zstd")`.
   - Return `len(combined)` after dedupe.
3. **`append_bars`** — `write_bars(path, bars, merge=True)` (live ingest entry point).
4. **`read_bars`** — `pq.read_table` → `to_pylist()` → `BarRecord.from_dict` per row.
5. **Query path** — `engine.py` uses DuckDB directly on globs for filtering/limits (does not call `read_bars`).

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| Compression | code constant | `zstd` | Parquet compression codec |
| `merge` flag | function arg | `True` | Overwrite vs replace semantics |

## 7. Worked examples

### Example A — happy path (backfill write)

```bash
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
python -c "
from pathlib import Path
from vinu_stock.storage import parquet
rows = parquet.read_bars(Path('data/prices/1m/AAPL/archive/2024.parquet'))
print(len(rows), rows[0].symbol, rows[0].bar_ts)
"
```

### Example B — edge case (idempotent rerun)

```bash
# Running backfill twice merges and dedupes — row count stable
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
```

### Example C — DuckDB external read

```bash
duckdb -c "
SELECT COUNT(*) AS n, MIN(bar_ts) AS min_ts, MAX(bar_ts) AS max_ts
FROM read_parquet('data/prices/1m/AAPL/archive/*.parquet')
"
```

## 8. API / CLI (if applicable)

Parquet I/O is internal. Indirect access:

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| GET | `/candles/{symbol}` | interval, days | Reads Parquet via DuckDB |
| — | `vinu-stock-backfill` | — | Writes archive Parquet |
| — | `vinu-stock-ingest --once` | — | Appends live Parquet |

## 9. SQL / queries (if applicable)

Equivalent DuckDB read used by query engine:

```sql
SELECT symbol, provider, bar_ts, open, high, low, close, volume,
       COALESCE(adj_factor, 1.0) AS adj_factor
FROM read_parquet(['data/prices/1m/AAPL/archive/*.parquet',
                   'data/prices/1m/AAPL/live/*.parquet'],
                  union_by_name=true)
WHERE symbol = 'AAPL'
ORDER BY bar_ts ASC
LIMIT 100;
```

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_parquet_io.py` | write, merge, dedupe, read round-trip |
| `tests/test_api.py` | End-to-end query over written parquet |

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Row count grew on rerun | Different `provider` same `bar_ts` | Expected — dedup is per provider |
| Corrupt parquet | Interrupted write | Delete file, rerun backfill year |
| `read_bars` slow on huge file | Full load to memory | Use DuckDB with `LIMIT` for exploration |

## 12. Fincept / reference repo mapping

| vinu-stock-price | Reference |
|------------------|-----------|
| zstd Parquet | Standard columnar store for OHLCV |
| Merge dedupe | Idempotent ingest pattern from data lake ETL |
| 11-column schema | Fincept `BrokerCandle` + metadata fields |

## 13. Related chapters

- [Chapter 09 — BarRecord Model](ch09-bar-record-model.md)
- [Chapter 08 — Data Layout](ch08-data-layout.md)
- [Chapter 13 — Backfill Flow](../part-3-ingest/ch13-backfill-flow.md)
- [Chapter 17 — Query Engine](../part-4-query/ch17-query-engine.md)
