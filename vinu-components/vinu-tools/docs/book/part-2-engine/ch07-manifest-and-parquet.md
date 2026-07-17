# Chapter 7 — Manifest and Parquet

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/engine/manifest.py`, `engine/engine.py` |
| **Status** | v1 |
| **Prerequisites** | ch06 |

## Run folder

```
data/runs/{id}_{slug}/
  manifest.md
  features.parquet
```

## manifest.md

Human audit trail: title, symbols, dates, preset, features, conditions, row count, column list.

## features.parquet

Columns: `ts`, `symbol`, `open`, `high`, `low`, `close`, `volume`, plus requested feature columns.

Rows are trimmed to `[from_ts, to_ts]` after indicator warm-up.
