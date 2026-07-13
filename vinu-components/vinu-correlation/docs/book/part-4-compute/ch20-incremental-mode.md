# Chapter 20 — Incremental vs full recompute

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/storage/backend.py` + `cli.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch19 |

## 1. Problem

Recomputing from scratch every time is wasteful. Incremental mode only processes data after the last computed timestamp, reducing API calls and compute time.

## 2. Mode selection

| Mode | Flag | Behavior |
|------|------|----------|
| Incremental | `--incremental` or default | Fetch news + price from `last_computed_ts`, append only new data |
| Full | `--force` | Ignore `last_computed_ts`, process full 30-day window |

## 3. How incremental works

```python
last_ts = self._storage.get_last_computed_ts(symbol)
# last_ts = max(ts) across all {year}.parquet files for the symbol
# If None, falls back to full compute
```

The `get_last_computed_ts` method scans all Parquet files in the symbol directory (excluding `_baseline` and `_correlation` files) and finds the maximum `ts`.

## 4. Dedup safety

Incremental appends may produce duplicate `(article_id, symbol)` pairs. The `_dedup_by_article_id` function in the storage backend handles this by keeping the most recent `computed_at` for each key.

## 5. CLI usage

```bash
vinu-correlation-compute AAPL                          # incremental (default)
vinu-correlation-compute AAPL --force                  # full recompute
vinu-correlation-compute AAPL --incremental             # explicit incremental
```
