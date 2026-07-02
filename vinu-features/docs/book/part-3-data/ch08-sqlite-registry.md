# Chapter 8 — SQLite Registry

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/storage/sqlite_backend.py` |
| **Status** | v1 |
| **Prerequisites** | ch05 |

## Table: feature_requests

| Column | Purpose |
|--------|---------|
| id | Primary key |
| title, slug | User label and folder slug |
| symbols, features | JSON arrays |
| from_ts, to_ts, interval | Query window |
| status | pending/running/done/failed/deleted |
| file_path | Run folder when done |
| request_hash | Dedup key |

Default DB: `VINU_FEATURES_META_DB_PATH` or `{data_dir}/meta.db`.

## Query patterns

- Latest by title: `get_latest_by_title`
- Pending queue: `claim_next_pending`
