# Chapter 20 — DuckDB SQL Cookbook

| Field | Value |
|-------|-------|
| **Package** | vinu-stock-price |
| **Module** | `vinu_stock/query/engine.py`, `vinu_stock/storage/paths.py` |
| **Status** | REVIEW |
| **Verified** | 2026-07-01 |
| **Prerequisites** | Chapter 08, Chapter 11, Chapter 17 |

## Learning objectives

- Run ad-hoc DuckDB queries over archive and live Parquet globs.
- Reproduce common research patterns: session filter, daily OHLC, provider mix, cross-symbol scans.
- Know when to use `vinu-stock-query` vs raw DuckDB CLI.

## 1. Problem this module solves

The HTTP API and `fetch_candles` cover routine access, but researchers often need **ad-hoc SQL** in a notebook or `duckdb` REPL: multi-symbol scans, custom joins with news events, or validation without writing Python. This chapter documents **DuckDB recipes** over the on-disk Parquet tree that mirror what `query/engine.py` does internally.

## 2. Position in pipeline

```mermaid
flowchart LR
  PQ[prices/1m/SYM/archive+live] --> DUCK[duckdb CLI / notebook]
  DUCK --> OUT[DataFrame or CSV]
  API[GET /candles] -.->|same files| PQ
```

| Step | Input | Output |
|------|-------|--------|
| `read_parquet([globs])` | symbol paths | Unified table |
| `union_by_name=true` | mixed schemas | Handles optional columns |
| Filter `bar_ts` | epoch range | Time window |
| Aggregate in SQL | optional | Custom buckets (API uses Python aggregate) |

## 3. File map

| File | Responsibility |
|------|----------------|
| `storage/paths.py` | `parquet_globs`, `archive_year_path`, `live_year_path` |
| `query/engine.py` | Reference SQL template |
| `storage/parquet.py` | Column names written to Parquet |
| `catalog/schema.sql` | Metadata in SQLite (join separately) |

## 4. Data contracts

### Parquet columns (typical)

| Field | Type | Example |
|-------|------|---------|
| `symbol` | string | `AAPL` |
| `provider` | string | `polygon` |
| `bar_ts` | int64 | UTC epoch seconds |
| `open`, `high`, `low`, `close` | float | OHLC |
| `volume` | float | Share volume |
| `vwap` | float | Optional |
| `trades` | int | Optional |
| `adj_factor` | float | Default 1.0 |

### Path layout

| Path | Content |
|------|---------|
| `{data_root}/prices/1m/{SYMBOL}/archive/{YEAR}.parquet` | Frozen year |
| `{data_root}/prices/1m/{SYMBOL}/live/{YEAR}.parquet` | Appended current year |

## 5. Logic (step by step)

1. Set `DATA=data/prices/1m` (or your `VINU_STOCK_DATA_ROOT`).
2. Use `read_parquet(['.../archive/*.parquet', '.../live/*.parquet'], union_by_name=true)`.
3. Filter `symbol` even when path is symbol-specific (defensive).
4. `bar_ts` is **UTC epoch** — convert with `to_timestamp(bar_ts)` or `epoch_ms(bar_ts * 1000)`.
5. For production parity with API, prefer `fetch_candles` for aggregation/indicators; SQL for exploration.
6. Attach `meta.db` in DuckDB to join catalog: `ATTACH 'data/meta.db' AS meta (TYPE SQLITE)`.

## 6. Configuration

| Key | YAML/env | Default | Effect |
|-----|----------|---------|--------|
| `VINU_STOCK_DATA_ROOT` | env | `./data` | Base for all paths below |
| DuckDB threads | session | auto | `SET threads TO 4;` in CLI |

## 7. Worked examples

### Example A — happy path (same window as API)

```bash
duckdb -c "
SELECT bar_ts, open, high, low, close, volume, provider
FROM read_parquet(['data/prices/1m/AAPL/archive/*.parquet', 'data/prices/1m/AAPL/live/*.parquet'], union_by_name=true)
WHERE bar_ts >= 1704067200 AND bar_ts <= 1704153600
ORDER BY bar_ts
LIMIT 20;
"
```

### Example B — edge case (provider breakdown)

```sql
SELECT provider,
       COUNT(*) AS bars,
       MIN(to_timestamp(bar_ts)) AS first_bar,
       MAX(to_timestamp(bar_ts)) AS last_bar
FROM read_parquet('data/prices/1m/AAPL/archive/2024.parquet')
GROUP BY provider;
```

### Example C — daily OHLC from 1m (SQL-only)

```sql
SELECT date_trunc('day', to_timestamp(bar_ts)) AS day,
       first(open ORDER BY bar_ts) AS open,
       max(high) AS high,
       min(low) AS low,
       last(close ORDER BY bar_ts) AS close,
       sum(volume) AS volume
FROM read_parquet(['data/prices/1m/AAPL/archive/*.parquet', 'data/prices/1m/AAPL/live/*.parquet'], union_by_name=true)
GROUP BY 1
ORDER BY 1 DESC
LIMIT 30;
```

### Example D — cross-symbol scan (all archived 2024)

```sql
SELECT symbol, count(*) AS n
FROM read_parquet('data/prices/1m/*/archive/2024.parquet', hive_partitioning=false)
GROUP BY symbol
ORDER BY n DESC;
```

## 8. API / CLI (if applicable)

| Method | Path / Command | Params | Response |
|--------|----------------|--------|----------|
| — | `duckdb` | SQL file | Ad-hoc analytics |
| — | `vinu-stock-query candles` | — | Wraps `fetch_candles` (preferred for API parity) |
| GET | `/candles/{symbol}` | `interval`, `days` | Aggregated + indicators in Python |

## 9. SQL / queries (if applicable)

**Recipe: last bar per symbol (catalog cross-check)**

```sql
ATTACH 'data/meta.db' AS meta (TYPE SQLITE);

SELECT c.symbol,
       c.last_bar_ts AS catalog_last,
       q.max_ts AS parquet_last
FROM meta.symbol_catalog c
LEFT JOIN (
  SELECT symbol, max(bar_ts) AS max_ts
  FROM read_parquet('data/prices/1m/*/live/2026.parquet', filename=true)
  GROUP BY symbol
) q ON c.symbol = q.symbol
WHERE c.last_bar_ts IS NOT NULL;
```

**Recipe: adjusted close in SQL**

```sql
SELECT bar_ts,
       close,
       adj_factor,
       close * COALESCE(adj_factor, 1.0) AS adj_close
FROM read_parquet('data/prices/1m/AAPL/archive/2024.parquet')
WHERE provider = 'yahoo'
ORDER BY bar_ts DESC
LIMIT 10;
```

**Recipe: RTH-only filter (approximate ET, no holiday table)**

```sql
SELECT *
FROM read_parquet('data/prices/1m/AAPL/live/2026.parquet')
WHERE extract(dow FROM to_timestamp(bar_ts) AT TIME ZONE 'America/New_York') BETWEEN 1 AND 5
  AND extract(hour FROM to_timestamp(bar_ts) AT TIME ZONE 'America/New_York') BETWEEN 9 AND 15
ORDER BY bar_ts DESC
LIMIT 100;
```

## 10. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_aggregate.py` | Python aggregation (parity reference) |
| `tests/test_parquet_io.py` | Columns exist for SQL |
| `tests/test_api.py` | End-to-end read path |

Ad-hoc SQL is manual; no dedicated cookbook test file.

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `No files found` | Wrong `DATA` path | Check `VINU_STOCK_DATA_ROOT` |
| Duplicate minutes | archive + live overlap | `DISTINCT ON (bar_ts)` or filter by path |
| Schema error | Old Parquet without `adj_factor` | `union_by_name=true` |
| Slow glob `*` | Many symbols | Query per-symbol or use catalog filter |

## 12. Fincept / reference repo mapping

| vinu-stock-price | Reference |
|------------------|-----------|
| DuckDB on Parquet | qlib / research notebooks pattern |
| `read_parquet` globs | Fincept DataHub local export style |
| SQL cookbook | FinRL feature engineering prep |

## 13. Related chapters

- [Chapter 17 — Query Engine](ch17-query-engine.md)
- [Chapter 18 — Aggregation](ch18-aggregation.md)
- [Chapter 08 — Data Layout](../part-2-storage/ch08-data-layout.md)
- [Chapter 11 — Parquet I/O](../part-2-storage/ch11-parquet-io.md)
