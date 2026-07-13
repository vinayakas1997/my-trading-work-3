# Chapter 15 — Parquet directory layout

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/storage/paths.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch16 |

## 1. Problem

Correlation data is persisted as Parquet files organized by symbol and year. The paths module provides a consistent mapping from logical data type to filesystem path.

## 2. Directory structure

```
{data_root}/
  correlation/
    AAPL/
      2026.parquet            -- Impact events
      2026_baseline.parquet   -- Baseline snapshots
      2026_correlation.parquet -- Correlation matrices
    MSFT/
      ...
```

## 3. Path functions

| Function | Returns | Example |
|----------|---------|---------|
| `impact_path(root, sym, year)` | `{root}/correlation/{sym}/{year}.parquet` | `data/correlation/AAPL/2026.parquet` |
| `baseline_path(root, sym, year)` | `{root}/correlation/{sym}/{year}_baseline.parquet` | `data/correlation/AAPL/2026_baseline.parquet` |
| `correlation_path(root, sym, year)` | `{root}/correlation/{sym}/{year}_correlation.parquet` | `data/correlation/AAPL/2026_correlation.parquet` |
| `symbol_dir(root, sym)` | `{root}/correlation/{sym}` | `data/correlation/AAPL` |
