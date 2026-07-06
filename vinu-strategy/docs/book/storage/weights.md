# Weight Storage

## Overview

Weight storage persists portfolio weights to Parquet files for historical analysis and backtesting.

## Storage Location

```
data/
  weights/
    {strategy_name}/
      {year}.parquet
```

**Example**:
```
data/
  weights/
    ma_crossover/
      2024.parquet
      2025.parquet
      2026.parquet
    rsi_mean_reversion/
      2025.parquet
      2026.parquet
```

## File Structure

Each Parquet file contains all weights for a strategy in a given year.

**Schema**:
```python
{
  "symbol": string,
  "weight": float64,
  "signal_value": float64,
  "run_id": string,
  "timestamp": timestamp[ns]
}
```

**Example Data**:
```
symbol  weight  signal_value  run_id                    timestamp
AAPL    0.25    0.1234        ma_crossover_20260706     2026-07-06 14:30:22
MSFT    0.25    0.0987        ma_crossover_20260706     2026-07-06 14:30:22
GOOGL   0.25    0.0456        ma_crossover_20260706     2026-07-06 14:30:22
```

## Operations

### Append Weights

**Method**: `WeightStorage.append_weights()`

**Parameters**:
- `strategy_name` (str): Strategy name
- `weights` (dict[str, float]): Current weights
- `signal_values` (dict[str, float]): Signal values per symbol
- `run_id` (str): Run identifier
- `metadata` (dict, optional): Additional metadata

**Example**:
```python
from vinu_strategy.storage.weights import WeightStorage

storage = WeightStorage(Path("./data"))
storage.append_weights(
    strategy_name="ma_crossover",
    weights={"AAPL": 0.25, "MSFT": 0.25},
    signal_values={"AAPL": 0.1234, "MSFT": 0.0987},
    run_id="ma_crossover_20260706_143022",
    metadata={"symbols": ["AAPL", "MSFT"], "count": 2}
)
```

**Behavior**:
1. Create directory if not exists
2. Load existing year file (if exists)
3. Append new weights
4. Write back to Parquet

**Performance**: O(n) where n = existing rows

### Read Weights

**Method**: `WeightStorage.read_weights()`

**Parameters**:
- `strategy_name` (str): Strategy name
- `symbol` (str, optional): Filter by symbol
- `from_ts` (int, optional): Start timestamp (Unix epoch)
- `to_ts` (int, optional): End timestamp (Unix epoch)

**Returns**: `pd.DataFrame`

**Example**:
```python
from vinu_strategy.storage.weights import WeightStorage

storage = WeightStorage(Path("./data"))

# Get all weights for strategy
df = storage.read_weights("ma_crossover")

# Get weights for specific symbol
df = storage.read_weights("ma_crossover", symbol="AAPL")

# Get weights for date range
df = storage.read_weights("ma_crossover", from_ts=1720000000, to_ts=1720086400)

print(df.head())
```

**Output**:
```
      symbol  weight  signal_value                  run_id            timestamp
0       AAPL    0.25        0.1234  ma_crossover_20260706  2026-07-06 14:30:22
1       MSFT    0.25        0.0987  ma_crossover_20260706  2026-07-06 14:30:22
2      GOOGL    0.25        0.0456  ma_crossover_20260706  2026-07-06 14:30:22
```

### Delete Weights

**Method**: `WeightStorage.delete_weights()`

**Parameters**:
- `strategy_name` (str): Strategy name
- `symbol` (str, optional): Delete only specific symbol

**Returns**: `int` - Number of rows deleted

**Example**:
```python
from vinu_strategy.storage.weights import WeightStorage

storage = WeightStorage(Path("./data"))

# Delete all weights for strategy
deleted = storage.delete_weights("ma_crossover")
print(f"Deleted {deleted} rows")

# Delete weights for specific symbol
deleted = storage.delete_weights("ma_crossover", symbol="AAPL")
print(f"Deleted {deleted} rows for AAPL")
```

## Performance Considerations

### Append Performance

**Current**: O(n) per append (reads entire file)

**Issue**: For large datasets (>1M rows), append becomes slow.

**Example**:
```
10,000 rows:    ~10ms
100,000 rows:   ~100ms
1,000,000 rows: ~1000ms
```

**Future Optimization**: Per-day files or append-only log.

### Read Performance

**Current**: O(m) where m = rows read

**Optimized**: Parquet column pruning and filtering.

**Example**:
```
Read all:       ~50ms for 100K rows
Filter by date: ~10ms for 100K rows
Filter by symbol: ~5ms for 100K rows
```

## Data Retention

### Weights

- **Retention**: Permanent (until deleted)
- **Organization**: By strategy and year
- **Compression**: Snappy codec

### Cleanup

**Manual**:
```bash
# Delete old weights
rm data/weights/ma_crossover/2024.parquet

# Delete entire strategy
rm -rf data/weights/ma_crossover/
```

**API**:
```python
storage.delete_weights("ma_crossover")
```

## Best Practices

### 1. Regular Cleanup

Delete old weights periodically:
```python
# Delete weights older than 1 year
from datetime import datetime, timedelta
cutoff = datetime.utcnow() - timedelta(days=365)
df = storage.read_weights("ma_crossover")
df = df[df['timestamp'] > cutoff]
# Rewrite with only recent data
```

### 2. Monitor Size

Track storage usage:
```bash
du -sh data/weights/*
```

### 3. Use Filters

Filter reads by symbol or date range to improve performance.

## API Integration

### Get Weights via HTTP

```bash
curl "http://localhost:8000/weights?strategy=ma_crossover&symbol=AAPL"
```

### Get Weights via Python

```python
from vinu_strategy.api import StrategyAPI

api = StrategyAPI()
weights = api.get_weights("ma_crossover", symbol="AAPL")
print(weights)
```

## Next Steps

- [Metadata Storage](metadata.md)
- [API Reference](../api-reference/http-api.md)
- [Testing Guide](../testing/test-guide.md)