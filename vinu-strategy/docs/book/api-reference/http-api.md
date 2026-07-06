# HTTP API Reference

## Overview

The vinu-strategy HTTP API provides REST endpoints for strategy management, evaluation, and data retrieval.

## Base URL

```
http://localhost:8000
```

## Authentication

No authentication required for local deployment. For production, add API key authentication.

## Endpoints

### Strategies

#### List Strategies

**Endpoint**: `GET /strategies`

**Description**: List all registered strategies.

**Response**: `200 OK`

**Response Body**:
```json
[
  {
    "name": "ma_crossover",
    "description": "9/21 SMA crossover strategy",
    "schedule": "daily",
    "enabled": true
  },
  {
    "name": "rsi_mean_reversion",
    "description": "RSI mean reversion strategy",
    "schedule": "weekly",
    "enabled": true
  }
]
```

**Example**:
```bash
curl http://localhost:8000/strategies
```

#### Get Strategy

**Endpoint**: `GET /strategies/{name}`

**Description**: Get details of a specific strategy.

**Parameters**:
- `name` (path, required): Strategy name

**Response**: `200 OK`

**Response Body**:
```json
{
  "name": "ma_crossover",
  "description": "9/21 SMA crossover strategy",
  "schedule": "daily",
  "features_required": ["sma_9", "sma_21"],
  "correlation_required": [],
  "pipeline": {
    "selection": {
      "method": "all"
    },
    "allocation": {
      "method": "signal_scaled",
      "signal": "sma_9 / sma_21 - 1"
    },
    "timing": {
      "method": "none"
    },
    "risk": {
      "method": "normalize",
      "max_weight": 0.25,
      "cash_floor": 0.10
    }
  }
}
```

**Error**: `404 Not Found` if strategy not found.

**Example**:
```bash
curl http://localhost:8000/strategies/ma_crossover
```

#### Evaluate Strategy

**Endpoint**: `POST /strategies/{name}/evaluate`

**Description**: Evaluate a strategy for specified symbols.

**Parameters**:
- `name` (path, required): Strategy name
- `symbols` (query, optional): Comma-separated list of symbols

**Request**: `POST`

**Response**: `200 OK`

**Response Body**:
```json
{
  "strategy_name": "ma_crossover",
  "run_id": "ma_crossover_20260706_143022",
  "timestamp": "2026-07-06T14:30:22.123456",
  "weights": [
    {"symbol": "AAPL", "weight": 0.25, "signal_value": 0.1234},
    {"symbol": "MSFT", "weight": 0.25, "signal_value": 0.0987},
    {"symbol": "GOOGL", "weight": 0.25, "signal_value": 0.0456}
  ],
  "metadata": {
    "symbol_count": 3,
    "weights": {
      "AAPL": 0.25,
      "MSFT": 0.25,
      "GOOGL": 0.25
    }
  },
  "rule_trace": {
    "AAPL": [
      {
        "rule": "ma_crossover",
        "fired": true,
        "conditions": [
          {
            "source": "features",
            "key": "SMA_9",
            "operator": "gt",
            "expected": "SMA_21",
            "reason": "175.50 > 172.30"
          }
        ],
        "action": {"type": "weight_add", "value": 0.05}
      }
    ]
  }
}
```

**Example**:
```bash
# Evaluate with default universe
curl -X POST http://localhost:8000/strategies/ma_crossover/evaluate

# Evaluate with specific symbols
curl -X POST "http://localhost:8000/strategies/ma_crossover/evaluate?symbols=AAPL,MSFT,GOOGL"
```

### Weights

#### Get Weights

**Endpoint**: `GET /weights`

**Description**: Get weight history for a strategy.

**Parameters**:
- `strategy` (query, default: "ma_crossover"): Strategy name
- `symbol` (query, optional): Filter by symbol
- `from_ts` (query, optional): Start timestamp (Unix epoch)
- `to_ts` (query, optional): End timestamp (Unix epoch)

**Response**: `200 OK`

**Response Body**:
```json
[
  {
    "symbol": "AAPL",
    "weight": 0.25,
    "signal_value": 0.1234,
    "run_id": "ma_crossover_20260706_143022",
    "timestamp": "2026-07-06T14:30:22.123456"
  },
  {
    "symbol": "MSFT",
    "weight": 0.25,
    "signal_value": 0.0987,
    "run_id": "ma_crossover_20260706_143022",
    "timestamp": "2026-07-06T14:30:22.123456"
  }
]
```

**Example**:
```bash
# Get all weights for ma_crossover
curl http://localhost:8000/weights?strategy=ma_crossover

# Get weights for specific symbol
curl "http://localhost:8000/weights?strategy=ma_crossover&symbol=AAPL"

# Get weights for date range
curl "http://localhost:8000/weights?strategy=ma_crossover&from_ts=1720000000&to_ts=1720086400"
```

#### Delete Weights

**Endpoint**: `DELETE /weights/{strategy}`

**Description**: Delete weight history for a strategy.

**Parameters**:
- `strategy` (path, required): Strategy name
- `symbol` (query, optional): Delete only specific symbol

**Response**: `200 OK`

**Response Body**:
```json
{
  "deleted": 150,
  "strategy": "ma_crossover",
  "symbol": null
}
```

**Example**:
```bash
# Delete all weights for strategy
curl -X DELETE http://localhost:8000/weights/ma_crossover

# Delete weights for specific symbol
curl -X DELETE "http://localhost:8000/weights/ma_crossover?symbol=AAPL"
```

### Runs

#### Get Runs

**Endpoint**: `GET /runs`

**Description**: Get run history for strategies.

**Parameters**:
- `strategy` (query, optional): Filter by strategy name

**Response**: `200 OK`

**Response Body**:
```json
[
  {
    "strategy_name": "ma_crossover",
    "run_id": "ma_crossover_20260706_143022",
    "symbol": "AAPL,MSFT,GOOGL",
    "timestamp": "2026-07-06T14:30:22.123456"
  },
  {
    "strategy_name": "ma_crossover",
    "run_id": "ma_crossover_20260706_120000",
    "symbol": "AAPL,MSFT",
    "timestamp": "2026-07-06T12:00:00.123456"
  }
]
```

**Example**:
```bash
# Get all runs
curl http://localhost:8000/runs

# Get runs for specific strategy
curl "http://localhost:8000/runs?strategy=ma_crossover"
```

#### Delete Runs

**Endpoint**: `DELETE /runs`

**Description**: Delete run history.

**Parameters**:
- `strategy` (query, optional): Delete runs for specific strategy

**Response**: `200 OK`

**Response Body**:
```json
{
  "deleted": 50,
  "strategy": null
}
```

**Example**:
```bash
# Delete all runs
curl -X DELETE http://localhost:8000/runs

# Delete runs for specific strategy
curl -X DELETE "http://localhost:8000/runs?strategy=ma_crossover"
```

#### Delete Run by ID

**Endpoint**: `DELETE /runs/{run_id}`

**Description**: Delete a specific run.

**Parameters**:
- `run_id` (path, required): Run ID

**Response**: `200 OK`

**Response Body**:
```json
{
  "deleted": true,
  "run_id": "ma_crossover_20260706_143022"
}
```

**Error**: `404 Not Found` if run not found.

**Example**:
```bash
curl -X DELETE http://localhost:8000/runs/ma_crossover_20260706_143022
```

### Settings

#### Get Settings

**Endpoint**: `GET /settings`

**Description**: Get server configuration.

**Response**: `200 OK`

**Response Body**:
```json
{
  "host": "0.0.0.0",
  "port": 8000,
  "data_root": "/home/user/vinu-strategy/data",
  "strategies_dir": "/home/user/vinu-strategy/strategies",
  "features_api_url": "http://localhost:8000",
  "correlation_api_url": "http://localhost:8001",
  "max_weight": 0.25,
  "cash_floor": 0.10,
  "rebalance_freq": "daily"
}
```

**Example**:
```bash
curl http://localhost:8000/settings
```

### Documentation

#### YAML Reference

**Endpoint**: `GET /docs/yaml-reference`

**Description**: Get YAML authoring guide.

**Response**: `200 OK`

**Content Type**: `text/markdown`

**Example**:
```bash
curl http://localhost:8000/docs/yaml-reference
```

## Error Responses

### 404 Not Found

```json
{
  "detail": "Strategy 'ma_crossover' not found"
}
```

### 400 Bad Request

```json
{
  "detail": "Invalid parameters"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

## Rate Limiting

No rate limiting for local deployment. For production, implement rate limiting.

## CORS

CORS enabled for all origins (development mode). For production, configure specific origins.

## Examples

### Complete Workflow

```bash
# 1. List strategies
curl http://localhost:8000/strategies

# 2. Get strategy details
curl http://localhost:8000/strategies/ma_crossover

# 3. Evaluate strategy
curl -X POST "http://localhost:8000/strategies/ma_crossover/evaluate?symbols=AAPL,MSFT"

# 4. Get weights
curl "http://localhost:8000/weights?strategy=ma_crossover"

# 5. Get runs
curl "http://localhost:8000/runs?strategy=ma_crossover"

# 6. Delete old weights
curl -X DELETE "http://localhost:8000/weights/ma_crossover"
```

### Python Example

```python
import requests

# Evaluate strategy
response = requests.post(
    "http://localhost:8000/strategies/ma_crossover/evaluate",
    params={"symbols": ["AAPL", "MSFT", "GOOGL"]}
)
result = response.json()

print(f"Run ID: {result['run_id']}")
for weight in result['weights']:
    print(f"{weight['symbol']}: {weight['weight']}")
```

### JavaScript Example

```javascript
// Evaluate strategy
fetch('http://localhost:8000/strategies/ma_crossover/evaluate?symbols=AAPL,MSFT', {
    method: 'POST'
})
.then(response => response.json())
.then(result => {
    console.log('Run ID:', result.run_id);
    result.weights.forEach(w => {
        console.log(`${w.symbol}: ${w.weight}`);
    });
});
```

## Next Steps

- [Python API Reference](python-api.md)
- [Strategy Authoring](../strategy-authoring/yaml-schema.md)
- [Deployment](../deployment/docker.md)