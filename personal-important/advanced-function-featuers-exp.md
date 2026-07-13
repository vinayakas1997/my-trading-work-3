# Advanced Features Specification for New Vinu Components

> **Purpose**: When building new components in the Vinu ecosystem, this document defines the mandatory and recommended advanced features to maintain consistency, reliability, and operational excellence across all components.

---

## Component Maturity Baseline (as of analysis date)

| Component | Maturity Level | Key Advanced Features |
|-----------|----------------|----------------------|
| **vinu-news** | ★★★★★ (Reference) | Background workers, queue backpressure, deduplication, multi-storage, WAL, schema migrations, health checks |
| **vinu-features** | ★★★★☆ | Hash deduplication, atomic claim-next-pending, worker loop, presets, migration system |
| **vinu-simulator** | ★★★★☆ | Benchmark comparison, custom strategies, result persistence |
| **vinu-correlation** | ★★★☆☆ | Strong statistical core, good tests, thin service layer |
| **vinu-strategy** | ★★★☆☆ | Rule trace, good engine, simpler storage, no WAL/background workers |
| **vinu-stock-price** | ★★★☆☆ | Solid provider abstraction, good CLI |
| **vinu-research** | ★☆☆☆☆ | Minimal - missing service facade, storage, tests, health, workers |

---

## Mandatory Features (Must Implement)

### 1. Service Facade Pattern
Every component **must** have a `Service` class that:
- Wraps all business logic
- Manages dependencies (clients, storage, config)
- Implements context manager (`__enter__`, `__exit__`)
- Has explicit `close()` method for resource cleanup
- Uses dependency injection for testability

```python
class NewComponentService:
    def __init__(self, config: NewComponentConfig, storage: StorageBackend = None, client: ExternalClient = None):
        self._config = config
        self._storage = storage or create_storage(config)
        self._owns_storage = storage is None
        self._client = client or ExternalClient(config.api_url)
    
    def __enter__(self) -> NewComponentService:
        return self
    
    def __exit__(self, *args: object) -> None:
        self.close()
    
    def close(self) -> None:
        if self._owns_storage:
            self._storage.close()
        if self._client:
            self._client.close()
```

### 2. Frozen Dataclass Configuration
Configuration **must** use frozen dataclasses with:
- Environment variable loading (`.env` + system env)
- Sensible defaults
- Type hints for all fields
- Factory function `load_config()`

```python
@dataclass(frozen=True)
class NewComponentConfig:
    host: str
    port: int
    data_root: Path
    api_url: str
    # ... all settings

def load_config() -> NewComponentConfig:
    _ensure_dotenv_loaded()
    return NewComponentConfig(
        host=os.environ.get("VINU_NEW_HOST", DEFAULT_HOST),
        # ...
    )
```

### 3. Thread-Local SQLite Connections with WAL
If using SQLite, **must** implement:
- `threading.local()` for per-thread connections
- `PRAGMA journal_mode=WAL` on every connection
- Lazy initialization of connection and stores

```python
def __init__(self, db_path: Path):
    self._db_path = db_path
    self._local = threading.local()

def _get_conn(self) -> sqlite3.Connection:
    conn = getattr(self._local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        self._local.conn = conn
    return conn
```

### 4. Health Endpoint with Dependency Verification
**Must** implement `health()` method that:
- Returns component status
- Actually pings downstream dependencies (not just config check)
- Includes storage info, version, dependency status

```python
def health(self) -> dict[str, Any]:
    info = self._storage.health_info()
    # ACTUALLY ping downstream services
    try:
        res = httpx.get(f"{self._config.downstream_url}/health", timeout=1.0)
        info["downstream_healthy"] = res.status_code == 200
    except Exception:
        info["downstream_healthy"] = False
    return info
```

### 5. Structured Error Logging
**Must** use `exc_info=True` for exception logging:
```python
LOG.warning("Operation failed for %s", item, exc_info=True)  # ✅ Good
LOG.warning("Operation failed for %s: %s", item, e)          # ❌ Bad - loses stack trace
```

### 6. CLI with Standard Subcommands
**Must** provide at minimum:
- `serve` - Start HTTP API server
- `query` / `read` - Query data
- `run` / `compute` - Execute core operation
- `list` - List runs/results
- `--json` flag for machine-readable output
- `--verbose` / debug logging

### 7. Test Suite with Fixtures
**Must** have:
- `tests/conftest.py` with shared fixtures
- Unit tests for core logic
- Integration tests for API endpoints
- Mock clients for external dependencies
- At least 5 test files covering different areas

---

## Strongly Recommended Features (Should Implement)

### 8. Request Deduplication (Hash-Based)
Prevent duplicate work by hashing request parameters:
```python
def _hash_request(req: SubmitRequest, features: list[str]) -> str:
    payload = {
        "symbols": sorted(req.symbols),
        "from_ts": req.from_ts,
        "to_ts": req.to_ts,
        "features": sorted(features),
        # ... all params that affect output
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

# Check before insert
existing = storage.get_by_hash(request_hash, status=STATUS_DONE)
if existing:
    return existing  # Return cached result
```

### 9. Atomic "Claim Next Pending" Pattern
For worker pools, use atomic claim to prevent duplicate processing:
```sql
UPDATE requests
SET status = 'running', updated_at = ?, error_message = NULL
WHERE id = (
    SELECT id FROM requests
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
)
RETURNING *
```

### 10. Schema Migration System
Track schema version with `PRAGMA user_version`:
```python
_SCHEMA_VERSION = 2

def _migrate(self, conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.execute("ALTER TABLE requests ADD COLUMN ml_model TEXT")
        conn.execute("ALTER TABLE requests ADD COLUMN ml_label TEXT")
        conn.execute("PRAGMA user_version=1")
    if version < 2:
        conn.execute("ALTER TABLE requests ADD COLUMN new_field TEXT")
        conn.execute("PRAGMA user_version=2")
    conn.commit()
```

### 11. Dry-Run Mode for All Mutating Operations
```python
def run_operation(self, *, dry_run: bool = False, ...) -> Result:
    if dry_run:
        return Result(preview_only=True, estimated_count=...)
    # Actual execution
```

### 12. Watchlist Sync from Shared File
Support cross-component watchlist sharing:
```python
def sync_watchlist_from_shared(self) -> dict:
    path = self._config.shared_watchlist_path
    if path is None:
        return {"ok": False, "message": "VINU_SHARED_WATCHLIST_PATH not set"}
    added = sync_from_shared(self._storage.watchlist, path)
    return {"ok": True, "added": added}
```

### 13. Background Worker with Queue Backpressure
For async/long-running operations:
```python
class BackgroundWorker:
    def __init__(self, concurrency: int, queue_maxsize: int = 1000):
        self.queue: queue.Queue[WorkItem] = queue.Queue(maxsize=queue_maxsize)
        self.workers = [Thread(target=self._worker_loop, daemon=True) for _ in range(concurrency)]
    
    def submit(self, item: WorkItem) -> bool:
        try:
            self.queue.put_nowait(item)
            return True
        except queue.Full:
            LOG.warning("Queue full, rejecting work")
            return False  # Backpressure signal
```

### 14. Rule Trace / Explainability
For decision-making components, output why decisions were made:
```python
result = OperationResult(
    decisions={...},
    rule_trace={
        "symbol": [
            {"rule": "rsi_oversold", "fired": True, "conditions": [...], "action": {"type": "buy", "weight": 0.1}}
        ]
    }
)
```

---

## Nice-to-Have Features (Enhancement)

### 15. Multiple Storage Backends
Factory pattern for SQLite / PostgreSQL / etc:
```python
def create_storage(storage: str, **kwargs) -> StorageBackend:
    if storage == "sqlite":
        return SqliteBackend(**kwargs)
    elif storage == "postgres":
        return PostgresBackend(**kwargs)
```

### 16. Benchmark Comparison in Results
For simulation/backtest components, compare against benchmarks:
```python
result.benchmark_metrics = {
    "SPY": {"total_return": 0.12, "sharpe": 1.2, "max_drawdown": -0.08},
    "QQQ": {"total_return": 0.15, "sharpe": 1.4, "max_drawdown": -0.10}
}
```

### 17. Idempotent Storage Writes
All persist operations should be idempotent (safe to retry):
```python
def persist(self, items: list[Item]) -> PersistResult:
    # Use INSERT OR IGNORE / ON CONFLICT DO UPDATE
    # Return counts: inserted, updated, skipped
```

### 18. Rate Limiting for External APIs
```python
from vinu_lib.rate_limit import TokenBucket

_rate_limiter = TokenBucket(rate=10, per=60)  # 10 req/min

def _rate_limited_request(self, ...):
    self._rate_limiter.take()
    return self._client.request(...)
```

---

## Component Initialization Checklist

When creating a new component, verify:

- [ ] `Service` class with context manager
- [ ] Frozen dataclass `Config` with `load_config()`
- [ ] Thread-local SQLite + WAL (if using SQLite)
- [ ] `health()` with real dependency checks
- [ ] `exc_info=True` logging everywhere
- [ ] CLI with `serve`, `query`, `run`, `list`
- [ ] `tests/conftest.py` + 5+ test files
- [ ] Request deduplication (hash-based)
- [ ] Atomic claim-next-pending (if workers)
- [ ] Schema migration with `user_version`
- [ ] Dry-run mode on all mutating ops
- [ ] Watchlist sync from shared file
- [ ] Background worker with backpressure (if async ops)
- [ ] Rule trace / explainability (if decisions)
- [ ] Storage factory for multiple backends
- [ ] Benchmark comparison (if simulations)
- [ ] Idempotent storage writes
- [ ] Rate limiting for external APIs

---

## Reference Implementation Files

Study these as templates:

| Pattern | Reference File |
|---------|----------------|
| Service Facade | `vinu-news/vinu_news/service.py` |
| Config | `vinu-news/vinu_news/config.py` |
| Thread-local + WAL | `vinu-features/vinu_features/storage/sqlite_backend.py` |
| Health Check | `vinu-news/vinu_news/service.py:health()` |
| CLI | `vinu-news/vinu_news/cli.py` |
| Tests | `vinu-features/tests/conftest.py` |
| Deduplication | `vinu-features/vinu_features/service.py:_hash_request()` |
| Claim Next Pending | `vinu-features/vinu_features/storage/sqlite_backend.py:claim_next_pending()` |
| Schema Migration | `vinu-features/vinu_features/storage/sqlite_backend.py:_migrate()` |
| Dry Run | `vinu-news/vinu_news/service.py:run_ingestion_cycle(dry_run=...)` |
| Watchlist Sync | `vinu-news/vinu_news/service.py:sync_watchlist_from_shared()` |
| Background Worker | `vinu-news/vinu_news/service.py:AutoAnalysisWorker` |
| Rule Trace | `vinu-strategy/vinu_strategy/service.py:evaluate()` |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-13 | Initial specification based on component audit |