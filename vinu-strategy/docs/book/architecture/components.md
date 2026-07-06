# Components

## Core Modules

### vinu_strategy/

#### service.py

**StrategyService** - Main orchestrator

```python
class StrategyService:
    def __init__(self, config: VinuStrategyConfig)
    def evaluate(strategy_name, symbols) -> StrategyResult
    def list_strategies() -> list[dict]
    def get_weights(strategy_name, symbol, from_ts, to_ts) -> list[dict]
    def get_runs(strategy_name) -> list[dict]
```

**Responsibilities**:
- Load strategies from YAML files
- Fetch features and correlation data
- Execute pipeline
- Store results

#### cli.py

**Command-line interface**

Commands:
- `serve` - Start HTTP API server
- `list` - List registered strategies
- `evaluate` - Run strategy evaluation
- `schedule` - Run periodic evaluations
- `reload` - Reload strategy YAML files

#### config.py

**Configuration management**

```python
class VinuStrategyConfig:
    features_api_url: str
    correlation_api_url: str
    host: str
    port: int
    data_root: Path
    strategies_dir: Path
    max_weight: float
    cash_floor: float
    rebalance_freq: str
```

### engine/

#### pipeline.py

**WeightPipeline** - 4-stage processing

```python
class WeightPipeline:
    def run(config, universe, feature_signals, correlation_signals, params)
```

**Stages**:
1. Selection
2. Allocation
3. Timing
4. Risk

#### selection.py

**Selection methods**

Methods:
- `all` - Pass all symbols
- `threshold` - Filter by signal threshold
- `top_n` - Keep top N by signal

```python
def select_threshold(universe, signals, field, min_val)
def select_top_n(universe, signals, field, n)
```

#### allocation.py

**Allocation methods**

Methods:
- `equal` - Equal weights
- `signal_scaled` - Proportional to signal

```python
def allocate_equal(candidates)
def allocate_signal_scaled(candidates, signals, signal_expr)
```

#### timing.py

**Timing methods**

Methods:
- `none` - No adjustments
- `rules` - Rule-based adjustments

```python
def run_rules(weights, candidates, signals, rules)
```

#### risk.py

**Risk methods**

Methods:
- `normalize` - Cap and scale
- `none` - Pass-through

```python
def risk_normalize(weights, params)
def risk_none(weights, params)
```

**Supports**:
- Long-only and long/short
- Max weight caps
- Cash floor reservation

#### rules_engine.py

**Rule evaluation**

```python
def evaluate_rules(candidates, signals, rules)
```

**Features**:
- AND logic for conditions
- Sequential rule evaluation
- Action execution (add, subtract, multiply, set)

### models/

#### strategy.py

**Strategy configuration**

```python
@dataclass
class StrategyConfig:
    name: str
    description: str
    schedule: str
    features_required: list[str]
    correlation_required: list[str]
    universe: dict
    pipeline: PipelineConfig

@dataclass
class PipelineConfig:
    selection: SelectionConfig
    allocation: AllocationConfig
    timing: TimingConfig
    risk: RiskConfig

@dataclass
class StrategyResult:
    strategy_name: str
    weights: dict[str, float]
    run_id: str
    timestamp: datetime
    metadata: dict
    rule_trace: dict
```

### storage/

#### weights.py

**Parquet weight storage**

```python
class WeightStorage:
    def append_weights(strategy_name, weights, signal_values, run_id, metadata)
    def read_weights(strategy_name, symbol, from_ts, to_ts) -> pd.DataFrame
    def delete_weights(strategy_name, symbol) -> int
```

**File structure**:
```
data/
  weights/
    ma_crossover/
      2024.parquet
      2025.parquet
      2026.parquet
```

#### meta.py

**SQLite metadata storage**

```python
class MetaStorage:
    def register_strategy(name, description, schedule)
    def log_run(strategy_name, run_id, symbol)
    def get_registered_strategies() -> list[dict]
    def get_runs(strategy_name) -> list[dict]
    def delete_runs(strategy_name) -> int
```

**Tables**:
- `strategies` - Strategy registry
- `runs` - Run history

### clients/

#### features_client.py

**vinu-features API client**

```python
class FeaturesClient:
    def get_features(symbol, indicators) -> dict
```

**Request**: `GET /features/{symbol}?indicators=rsi_14,sma_20`

**Response**:
```json
{
  "symbol": "AAPL",
  "values": {
    "rsi_14": 45.2,
    "sma_20": 175.50,
    "signal": 0.123
  }
}
```

#### correlation_client.py

**vinu-correlation API client**

```python
class CorrelationClient:
    def get_impact(symbol) -> dict
    def get_correlation(symbol) -> dict
    def get_drawdown(symbol) -> dict
```

**Response types**:
- `impact`: News impact data
- `correlation`: Pearson correlation with news
- `drawdown`: Drawdown attribution

### server/

#### app.py

**FastAPI application**

```python
def create_app() -> FastAPI
```

**Routes**:
- `/strategies` - List strategies
- `/strategies/{name}` - Get strategy
- `/strategies/{name}/evaluate` - Evaluate strategy
- `/weights` - Get weight history
- `/runs` - Get run history

#### routes_read.py

**Read-only endpoints**

Endpoints:
- `GET /strategies`
- `GET /strategies/{name}`
- `POST /strategies/{name}/evaluate`
- `GET /weights`
- `GET /runs`
- `DELETE /weights/{strategy}`
- `DELETE /runs`
- `DELETE /runs/{run_id}`

#### routes_config.py

**Configuration endpoints**

Endpoints:
- `GET /settings` - Get server configuration

## Data Models

### StrategyConfig

```yaml
name: ma_crossover
description: "9/21 SMA crossover"
schedule: daily
features_required:
  - sma_9
  - sma_21
universe:
  source: inline
  inline: [AAPL, MSFT, GOOGL]
pipeline:
  selection:
    method: all
  allocation:
    method: signal_scaled
  timing:
    method: none
  risk:
    method: normalize
```

### StrategyResult

```python
{
  "strategy_name": "ma_crossover",
  "run_id": "ma_crossover_20260706_143022",
  "timestamp": "2026-07-06T14:30:22",
  "weights": [
    {"symbol": "AAPL", "weight": 0.25, "signal_value": 0.123}
  ],
  "metadata": {
    "symbol_count": 3,
    "weights": {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25}
  },
  "rule_trace": {
    "AAPL": [
      {
        "rule": "oversold_boost",
        "fired": true,
        "conditions": [
          {"source": "features", "key": "RSI_14", "operator": "lt", 
           "expected": 30, "reason": "45.2 >= 30"}
        ],
        "action": {"type": "weight_add", "value": 0.05}
      }
    ]
  }
}
```

## Extension Points

### Custom Pipeline Methods

Register custom methods:

```python
# In your code
from vinu_strategy.engine.selection import SELECTION_METHODS

def custom_selection(universe, signals, params):
    # Custom logic
    return [sym for sym in universe if should_include(sym, signals[sym])]

SELECTION_METHODS["custom"] = custom_selection
```

### Custom Storage

Override storage:

```python
from vinu_strategy.storage.weights import WeightStorage

class CustomStorage(WeightStorage):
    def append_weights(self, strategy_name, weights, ...):
        # Custom storage logic
        pass
```

### Custom Clients

Override clients:

```python
from vinu_strategy.clients.features_client import FeaturesClient

class CustomFeaturesClient(FeaturesClient):
    def get_features(self, symbol, indicators):
        # Custom API logic
        pass
```

## Module Dependencies

```
service.py
  -> engine/pipeline.py
  -> engine/selection.py
  -> engine/allocation.py
  -> engine/timing.py
  -> engine/risk.py
  -> engine/rules_engine.py
  -> clients/features_client.py
  -> clients/correlation_client.py
  -> storage/weights.py
  -> storage/meta.py
  -> models/strategy.py

cli.py
  -> api.py
  -> server/app.py

api.py
  -> service.py

server/app.py
  -> server/routes_read.py
  -> server/routes_config.py
```

## Thread Safety

- **Feature fetching**: Thread-safe with ThreadPoolExecutor
- **Client instances**: Thread-safe with locks in base.py
- **Storage writes**: Thread-safe with locks
- **Pipeline execution**: Single-threaded per evaluation

## Performance Characteristics

| Component | Complexity | Notes |
|-----------|------------|-------|
| Service.evaluate | O(n) | n = universe size |
| Pipeline.run | O(n) | Linear per stage |
| Rules evaluation | O(n * r) | r = rules per symbol |
| Storage append | O(1) | Parquet append |
| Storage read | O(m) | m = rows read |