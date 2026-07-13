# Metadata Storage

## Overview

Metadata storage persists run history and strategy registry in SQLite database.

## Database Location

```
data/meta.db
```

## Tables

### Strategies Table

**Schema**:
```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    schedule TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes**:
- `name` (UNIQUE)

**Example Data**:
```
id  name                description                    schedule
1   ma_crossover        9/21 SMA crossover strategy    daily
2   rsi_mean_reversion  RSI mean reversion             weekly
3   news_aware_momentum Momentum with news corr      daily
```

### Runs Table

**Schema**:
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    run_id TEXT NOT NULL,
    symbol TEXT,
    timestamp DATETIME,
    FOREIGN KEY (strategy_name) REFERENCES strategies(name)
);
```

**Indexes**:
- `strategy_name`
- `run_id` (UNIQUE)
- `timestamp`

**Example Data**:
```
id  strategy_name         run_id                        symbol           timestamp
1   ma_crossover          ma_crossover_20260706_143022  AAPL,MSFT,GOOGL 2026-07-06 14:30:22
2   ma_crossover          ma_crossover_20260706_120000  AAPL,MSFT       2026-07-06 12:00:00
3   rsi_mean_reversion    rsi_mean_reversion_20260706 RSI_14,MSFT     2026-07-06 14:30:22
```

## Operations

### Register Strategy

**Method**: `MetaStorage.register_strategy()`

**Parameters**:
- `name` (str): Strategy name
- `description` (str): Human-readable description
- `schedule` (str): Rebalance frequency

**Example**:
```python
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))
storage.register_strategy(
    name="ma_crossover",
    description="9/21 SMA crossover strategy",
    schedule="daily"
)
```

**Behavior**:
1. Insert or update strategy record
2. Set `updated_at` timestamp

### Log Run

**Method**: `MetaStorage.log_run()`

**Parameters**:
- `strategy_name` (str): Strategy name
- `run_id` (str): Run identifier
- `symbol` (str): Comma-separated symbol list

**Example**:
```python
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))
storage.log_run(
    strategy_name="ma_crossover",
    run_id="ma_crossover_20260706_143022",
    symbol="AAPL,MSFT,GOOGL"
)
```

**Behavior**:
1. Insert run record
2. Auto-increment ID

### Get Registered Strategies

**Method**: `MetaStorage.get_registered_strategies()`

**Returns**: `list[dict]`

**Example**:
```python
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))
strategies = storage.get_registered_strategies()

for s in strategies:
    print(f"{s['name']}: {s['description']} ({s['schedule']})")
```

**Output**:
```
ma_crossover: 9/21 SMA crossover strategy (daily)
rsi_mean_reversion: RSI mean reversion (weekly)
news_aware_momentum: Momentum with news corr (daily)
```

### Get Runs

**Method**: `MetaStorage.get_runs()`

**Parameters**:
- `strategy_name` (str, optional): Filter by strategy

**Returns**: `list[dict]`

**Example**:
```python
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))

# Get all runs
runs = storage.get_runs()

# Get runs for specific strategy
runs = storage.get_runs("ma_crossover")

for run in runs:
    print(f"{run['run_id']}: {run['symbol']} @ {run['timestamp']}")
```

**Output**:
```
ma_crossover_20260706_143022: AAPL,MSFT,GOOGL @ 2026-07-06 14:30:22
ma_crossover_20260706_120000: AAPL,MSFT @ 2026-07-06 12:00:00
```

### Delete Runs

**Method**: `MetaStorage.delete_runs()`

**Parameters**:
- `strategy_name` (str, optional): Delete runs for specific strategy

**Returns**: `int` - Number of rows deleted

**Example**:
```python
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))

# Delete all runs
deleted = storage.delete_runs()
print(f"Deleted {deleted} runs")

# Delete runs for specific strategy
deleted = storage.delete_runs("ma_crossover")
print(f"Deleted {deleted} runs for ma_crossover")
```

### Delete Run by ID

**Method**: `MetaStorage.delete_run_by_id()`

**Parameters**:
- `run_id` (str): Run identifier

**Returns**: `bool` - True if deleted, False if not found

**Example**:
```python
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))

deleted = storage.delete_run_by_id("ma_crossover_20260706_143022")
print(f"Deleted: {deleted}")
```

## Database Schema Version

Current schema version: `1`

**Migration**: No migrations needed for initial release.

## Performance

### Query Performance

| Query | Rows | Time |
|-------|------|------|
| Get all strategies | 10 | ~1ms |
| Get all runs | 10,000 | ~10ms |
| Get runs by strategy | 1,000 | ~5ms |
| Insert run | 1 | ~1ms |

### Index Usage

- `strategy_name` index for filtering
- `run_id` index for unique lookups
- `timestamp` index for date range queries

## Data Retention

### Strategies

- **Retention**: Permanent (until deleted)
- **Updates**: Updated on strategy YAML changes

### Runs

- **Retention**: Permanent (until deleted)
- **Growth**: Grows with evaluations

**Recommendation**: Periodic cleanup of old runs.

### Cleanup Example

```python
from datetime import datetime, timedelta
from vinu_strategy.storage.meta import MetaStorage

storage = MetaStorage(Path("./data/meta.db"))

# Delete runs older than 1 year
cutoff = datetime.utcnow() - timedelta(days=365)
# Note: Implement custom query for date-based deletion
```

## API Integration

### Get Strategies via HTTP

```bash
curl http://localhost:8000/strategies
```

### Get Runs via HTTP

```bash
curl "http://localhost:8000/runs?strategy=ma_crossover"
```

### Get Runs via Python

```python
from vinu_strategy.api import StrategyAPI

api = StrategyAPI()
runs = api.get_runs("ma_crossover")
print(runs)
```

## Best Practices

### 1. Regular Cleanup

Delete old runs periodically:
```python
# Delete runs older than 90 days
cutoff = datetime.utcnow() - timedelta(days=90)
# Implement custom cleanup query
```

### 2. Monitor Database Size

```bash
du -sh data/meta.db
sqlite3 data/meta.db "SELECT COUNT(*) FROM runs;"
```

### 3. Backup Database

```bash
cp data/meta.db data/meta.db.backup
```

## Next Steps

- [Weight Storage](weights.md)
- [API Reference](../api-reference/http-api.md)
- [Testing Guide](../testing/test-guide.md)