# Data Flow

## End-to-End Flow

This document describes the complete data flow from strategy configuration to portfolio weights output.

## Flow Diagram

```
┌──────────────┐
│ Strategy YAML│
└──────┬───────┘
       |
       v
┌───────────────────────────────────────┐
│     StrategyService.__init__()        |
│  - Load all YAML files                |
│  - Register in metadata DB            |
│  - Initialize clients                 |
└───────────────────────────────────────┘
       |
       v
┌───────────────────────────────────────┐
│     Service.evaluate()                |
│  - Get strategy config                |
│  - Resolve universe                   |
│  - Fetch features (parallel)          |
│  - Fetch correlations (parallel)      |
└───────────────────────────────────────┘
       |
       v
┌───────────────────────────────────────┐
│     Pipeline.run()                    |
│  - Selection                          |
│  - Allocation                         |
│  - Timing                             |
│  - Risk                               |
└───────────────────────────────────────┘
       |
       v
┌───────────────────────────────────────┐
│     Storage                           |
│  - Append weights to Parquet          |
│  - Log run to metadata DB             |
└───────────────────────────────────────┘
       |
       v
┌───────────────────────────────────────┐
│     StrategyResult                    |
│  - Return to caller                   |
└───────────────────────────────────────┘
```

## Step 1: Strategy Loading

### Location: `service.py::_sync_registry()`

```python
def _sync_registry(self) -> None:
    for name, scfg in self._registry._strategies.items():
        self._meta_storage.register_strategy(
            name, 
            scfg.description, 
            scfg.schedule
        )
```

**Process**:
1. Load all YAML files from `strategies_dir`
2. Parse each into `StrategyConfig`
3. Register in SQLite `strategies` table

**Metadata stored**:
- `name` - Strategy identifier
- `description` - Human-readable description
- `schedule` - Rebalance frequency

## Step 2: Universe Resolution

### Location: `service.py::_resolve_universe()`

```python
def _resolve_universe(self, config, symbols) -> list[str]:
    if symbols:
        return symbols  # Override with provided symbols
    source = config.universe.get("source", "watchlist")
    if source == "watchlist" and self._config.shared_watchlist_path:
        with open(self._config.shared_watchlist_path) as f:
            return json.load(f)
    return config.universe.get("inline", DEFAULT_UNIVERSE)
```

**Universe sources**:
1. **Override**: Explicit symbols passed to `evaluate()`
2. **Watchlist**: External JSON file
3. **Inline**: Defined in strategy YAML

**Default universe**: `["AAPL", "MSFT", "GOOGL", "AMZN", "META"]`

## Step 3: Feature Fetching

### Location: `service.py::evaluate()`

```python
feature_signals: dict[str, dict[str, float]] = {}
if config.features_required:
    with ThreadPoolExecutor(max_workers=10) as pool:
        fut_to_sym = {
            pool.submit(self._features_client.get_features, sym, indicators=config.features_required): sym
            for sym in universe
        }
        for fut in as_completed(fut_to_sym):
            sym = fut_to_sym[fut]
            data = fut.result()
            if data:
                feature_signals[sym] = self._extract_feature_values(data, config.features_required)
```

**Process**:
1. Create futures for each symbol
2. Execute in parallel (max 10 workers)
3. Extract only requested indicators
4. Handle failures gracefully (empty dict)

**Feature extraction**:
```python
def _extract_feature_values(self, data, indicators):
    result = {}
    values = data.get("values", data)
    values_dict = {k.lower(): v for k, v in values.items()}
    for ind in indicators:
        raw = values_dict.get(ind.lower())
        result[ind] = float(raw) if raw is not None else 0.0
    return result
```

**Case normalization**: All keys lowercased for consistency.

## Step 4: Correlation Fetching

### Location: `service.py::_fetch_correlation_for_symbol()`

```python
def _fetch_correlation_for_symbol(self, sym, required):
    ctx = {}
    if "impact" in required:
        ctx["impact"] = self._correlation_client.get_impact(sym)
    if "granger" in required or "correlation" in required:
        ctx["correlation"] = self._correlation_client.get_correlation(sym)
    if "drawdown" in required:
        ctx["drawdown"] = self._correlation_client.get_drawdown(sym)
    return self._flatten_correlation_context(ctx)
```

**Flattening**: Nested dicts are flattened to single level:

```python
def _flatten_correlation_context(self, ctx):
    flat = {}
    for key, value in ctx.items():
        if isinstance(value, dict):
            flat.update(value)
        else:
            flat[key] = value
    return flat
```

**Example**:
```python
# Input: {"impact": {"high_impact_bullish_events": 3}}
# Output: {"high_impact_bullish_events": 3}
```

## Step 5: Pipeline Execution

### Location: `engine/pipeline.py`

```python
def run(self, config, universe, feature_signals, correlation_signals, params):
    # Stage 1: Selection
    candidates = self.run_selection(config, universe, feature_signals)
    
    # Stage 2: Allocation
    weights = self.run_allocation(config, candidates, feature_signals, params)
    
    # Stage 3: Timing
    weights = self.run_timing(config, weights, candidates, feature_signals)
    
    # Stage 4: Risk
    weights = self.run_risk(config, weights, params)
    
    return weights, pipeline_meta
```

**Data passed between stages**:
- **Selection**: `universe` -> `candidates`
- **Allocation**: `candidates` + `feature_signals` -> `weights`
- **Timing**: `weights` + `feature_signals` + `rules` -> `adjusted_weights`
- **Risk**: `adjusted_weights` + `params` -> `final_weights`

## Step 6: Storage

### Weight Storage

### Location: `storage/weights.py`

```python
def append_weights(self, strategy_name, weights, signal_values, run_id, metadata):
    df = pd.DataFrame([
        {
            "symbol": sym,
            "weight": w,
            "signal_value": signal_values.get(sym, 0.0),
            "run_id": run_id,
            "timestamp": datetime.utcnow()
        }
        for sym, w in weights.items()
    ])
    
    # Append to year-based Parquet file
    year = datetime.utcnow().year
    path = self._weights_dir / strategy_name / f"{year}.parquet"
    append_to_parquet(path, df)
```

**File structure**:
```
data/
  weights/
    ma_crossover/
      2024.parquet  # All 2024 weights
      2025.parquet
      2026.parquet
```

**Parquet schema**:
```python
symbol: string
weight: float64
signal_value: float64
run_id: string
timestamp: timestamp
```

### Metadata Storage

### Location: `storage/meta.py`

```python
def log_run(self, strategy_name, run_id, symbol):
    self._conn.execute(
        """INSERT INTO runs (strategy_name, run_id, symbol, timestamp)
           VALUES (?, ?, ?, ?)""",
        (strategy_name, run_id, symbol, datetime.utcnow())
    )
```

**Runs table**:
```sql
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT,
    run_id TEXT,
    symbol TEXT,
    timestamp DATETIME
)
```

## Step 7: Result Construction

### Location: `service.py::evaluate()`

```python
result = StrategyResult(
    strategy_name=strategy_name,
    weights=self._weights_to_dataframe(weights, signal_values),
    run_id=actual_run_id,
    timestamp=datetime.utcnow(),
    metadata={"symbol_count": len(universe), "weights": weights},
    rule_trace=pipeline_meta.get("rule_trace", {}),
)
```

**Result components**:
1. **weights**: DataFrame with symbol, weight, signal_value
2. **run_id**: Unique identifier for this evaluation
3. **metadata**: Additional context
4. **rule_trace**: Detailed rule evaluation (if `--trace` enabled)

## Error Handling Flow

```
┌───────────────────────────────────────┐
│  Feature fetch fails                  |
└───────────────┬───────────────────────┘
                |
                v
┌───────────────────────────────────────┐
│  Return empty dict for that symbol    |
│  Continue with other symbols          |
└───────────────┬───────────────────────┘
                |
                v
┌───────────────────────────────────────┐
│  Pipeline processes available data    |
│  Symbols with no features get 0 weight|
└───────────────┬───────────────────────┘
                |
                v
┌───────────────────────────────────────┐
│  Log warning to run history           |
└───────────────────────────────────────┘
```

## Performance Optimization

### Parallel Fetching

```python
with ThreadPoolExecutor(max_workers=10) as pool:
    # Fetch features and correlations in parallel
    futures = [...]
    for fut in as_completed(futures):
        process_result(fut)
```

**Benefits**:
- 10x faster for large universes
- Non-blocking I/O

### Caching

**Not implemented yet**, but planned:
- Feature cache (TTL-based)
- Correlation cache
- Weight cache for recent runs

## Data Transformations

### Feature Signals

**Input** (from API):
```json
{
  "symbol": "AAPL",
  "values": {
    "sma_9": 175.50,
    "sma_21": 172.30,
    "signal": 0.123
  }
}
```

**Extracted** (for pipeline):
```python
{
  "sma_9": 175.50,
  "sma_21": 172.30,
  "signal": 0.123
}
```

### Correlation Signals

**Input** (from API):
```json
{
  "impact": {
    "high_impact_bullish_events": 3
  },
  "correlation": {
    "news_return_corr": 0.45
  }
}
```

**Flattened** (for pipeline):
```python
{
  "high_impact_bullish_events": 3,
  "news_return_corr": 0.45
}
```

## Timing and Ordering

### Sequential Stages

Pipeline stages execute sequentially:
1. Selection must complete before allocation
2. Allocation must complete before timing
3. Timing must complete before risk

**Reason**: Each stage depends on output of previous stage.

### Parallel Fetching

Feature and correlation fetching are parallel:
- All feature fetches run concurrently
- All correlation fetches run concurrently
- Both can run simultaneously

## Data Lifecycle

```
Strategy YAML
    |
    v
In-memory config (StrategyService)
    |
    v
Feature/Correlation data (temporary)
    |
    v
Pipeline weights (temporary)
    |
    v
Parquet storage (persistent)
    |
    v
Metadata DB (persistent)
```

**Cleanup**:
- Feature/correlation data: Discarded after evaluation
- Weights: Retained in Parquet files
- Metadata: Retained in SQLite until deleted

## Monitoring

### Logs

Key log points:
- Strategy loaded
- Universe resolved
- Features fetched (count)
- Correlations fetched (count)
- Weights generated (count)
- Weights stored

### Metrics

**Planned**:
- Evaluation duration
- Feature fetch latency
- Correlation fetch latency
- Pipeline stage duration
- Storage write time

## Debugging

### Enable Trace

```bash
vinu-strategy evaluate ma_crossover AAPL --trace
```

**Output**:
```
Rule Trace:
============================================================

AAPL:
  + RSI_14
    features.RSI_14 lt 30 -> 45.2 >= 30 (false)
  - SMA_9
    features.SMA_9 gt SMA_21 -> 175.50 > 172.30 (true)
    -> action: weight_add(0.05), weight_after=0.30
```

### Inspect Data

```python
# Inspect feature signals
print(feature_signals["AAPL"])
# {'sma_9': 175.50, 'sma_21': 172.30, 'signal': 0.123}

# Inspect correlation signals
print(correlation_signals["AAPL"])
# {'high_impact_bullish_events': 3, 'news_return_corr': 0.45}
```

## Next Steps

- [Architecture Overview](overview.md)
- [Pipeline Design](pipeline.md)
- [Strategy Authoring](../strategy-authoring/yaml-schema.md)