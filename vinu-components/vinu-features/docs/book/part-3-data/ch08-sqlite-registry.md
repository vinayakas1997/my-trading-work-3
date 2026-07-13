# Chapter 8 - SQLite Registry

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
| ml_model | ML model name (optional) |
| ml_label | ML label column (optional) |

Default DB: `VINU_FEATURES_META_DB_PATH` or `{data_dir}/meta.db`.

## Thread-Safe Storage

The storage layer uses per-thread connections with WAL mode for concurrent access:

```python
class SqliteBackend:
    def __init__(self, db_path: Path):
        self._local = threading.local()
        self._init_connection()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._migrate(conn)
            self._local.conn = conn
        return conn
```

### Benefits

- **Thread safety**: Each thread has its own connection
- **WAL mode**: Write-ahead logging for better concurrency
- **Automatic migrations**: Schema upgrades handled transparently
- **Connection pooling**: Connections reused per thread

### Migration System

Schema version tracked via `PRAGMA_version`:

```python
def _migrate(self, conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA_version").fetchone()[0]
    if version == 0:
        # Add ml_model, ml_label columns
        conn.execute("ALTER TABLE feature_requests ADD COLUMN ml_model TEXT")
        conn.execute("ALTER TABLE feature_requests ADD COLUMN ml_label TEXT")
        conn.execute("PRAGMA_version=1")
    conn.commit()
```

## Query patterns

- Latest by title: `get_latest_by_title`
- Pending queue: `claim_next_pending`
- List with filters: `list_requests(status="done", title="AAPL")`
- By hash: `get_by_hash(request_hash, status="done")`