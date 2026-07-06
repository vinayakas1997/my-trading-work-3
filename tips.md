# Vinu Component Guidelines

## Thread Safety (SQLite)

- Use `threading.local()` — each thread gets its own connection via `_get_conn()` pattern
- Enable WAL mode: `PRAGMA journal_mode=WAL` on every new connection
- Do NOT use `check_same_thread=False`
- Cache per-thread stores as properties on `self._local`
- Schema init (`CREATE TABLE IF NOT EXISTS`) runs once on the main thread; subsequent threads connect to the existing DB

```python
import threading

class MyBackend:
    def __init__(self, db_path):
        self.db_path = db_path
        self._local = threading.local()
        conn = self._get_conn()
        self._init_schema(conn)

    def _get_conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    @property
    def stores(self):
        if not hasattr(self._local, "_stores"):
            self._local._stores = MyStore(self._get_conn())
        return self._local._stores
```

## Parallelism

- Use `concurrent.futures.ThreadPoolExecutor` for parallel I/O
- Cap workers with `min(len(items), 4)`
- Protect shared accumulators with `threading.Lock()`
- Never share SQLite connections across threads (each thread gets its own via `_get_conn()`)
- For background jobs, use `threading.Thread(target=..., daemon=True)` with a status dict and lock

## Schema Migrations

- Use `vinu_lib.db` helpers: `migrate_schema()`, `add_columns()`
- Track schema version via `PRAGMA user_version`
- Always wrap `ALTER TABLE ADD COLUMN` in try/except for idempotency

```python
from vinu_lib.db import migrate_schema, add_columns

def _migrate(conn):
    migrate_schema(conn, version=1, migrations=[
        ("ALTER TABLE items ADD COLUMN ml_model TEXT", "add ml_model"),
    ])
    add_columns(conn, "items", [
        ("ml_label", "TEXT"),
    ])
```

## Project Structure

| Convention | Standard |
|------------|----------|
| Language | Python 3.10+, FastAPI |
| Packaging | Each module is an independent package with `pyproject.toml` |
| CLI | Entry points under `[project.scripts]` in `pyproject.toml` |
| API Ports | Incremental: news=8080, stock-price=8081, features=8082 |
| Web UI | `web/` directory with Vite + React, build to `server/static/` |
| Tests | `tests/` directory mirroring source, pytest |
| Docker | Each module has its own `Dockerfile`; root `docker-compose.yml` adds services |

## Environment Variables

- Load via `python-dotenv` from `.env` file
- Config stored as frozen dataclass, loaded in `config.py`

## Indicator Caching

- Use `vinu_lib.cache.LruCache` or the `IndicatorCache` pattern from `vinu-stock-price`
- Key by `(symbol, interval, time_range, indicator_set, adjusted)`
- Default TTL: 300s for live data
- Define `invalidate(symbol=None)` to clear on new data

## Cross-Module Integration

- `vinu-features` depends on `vinu-stock-price` HTTP API for candle data
- `vinu-news` depends on `vinu-stock-price` HTTP API for price reaction data
- Watchlist sync via shared JSON file (`VINU_SHARED_WATCHLIST_PATH`)
- Use Docker service names (e.g., `http://stock-api:8081`) for cross-container communication
