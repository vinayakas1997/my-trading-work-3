# Chapter 12 — Config and Environment

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/config.py` |
| **Status** | v1 |
| **Prerequisites** | ch01 |

## Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VINU_FEATURES_DATA_DIR` | `./data` | Run artifact root |
| `VINU_FEATURES_META_DB_PATH` | `{data}/meta.db` | SQLite registry |
| `VINU_STOCK_API_URL` | `http://127.0.0.1:8081` | OHLCV source |
| `VINU_FEATURES_HOST` | `127.0.0.1` | HTTP bind |
| `VINU_FEATURES_PORT` | `8082` | HTTP port |

See [`.env.example`](../../../.env.example).
