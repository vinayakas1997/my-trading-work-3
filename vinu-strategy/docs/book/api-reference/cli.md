# CLI Reference

## Overview

The vinu-strategy CLI provides command-line access to strategy evaluation, management, and monitoring.

## Installation

```bash
pip install vinu-strategy
```

## Commands

### `serve` - Start HTTP API Server

Starts the FastAPI server with HTTP API endpoints.

**Usage**:
```bash
vinu-strategy serve [OPTIONS]
```

**Options**:
- `--host TEXT` - Host to bind to (default: from config)
- `--port INTEGER` - Port to bind to (default: from config)

**Example**:
```bash
# Use config defaults
vinu-strategy serve

# Custom host and port
vinu-strategy serve --host 0.0.0.0 --port 9000
```

**Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [1234]
INFO:     Started server process [1235]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**API Endpoints**:
- `GET /strategies` - List strategies
- `GET /strategies/{name}` - Get strategy details
- `POST /strategies/{name}/evaluate` - Evaluate strategy
- `GET /weights` - Get weight history
- `GET /runs` - Get run history
- `DELETE /weights/{strategy}` - Delete weight history
- `DELETE /runs` - Delete run history

### `list` - List Registered Strategies

Lists all registered strategies with their schedules.

**Usage**:
```bash
vinu-strategy list
```

**Output**:
```
Name                     Schedule   Enabled  Description
--------------------------------------------------------------------------------
ma_crossover             daily      YES      9/21 SMA crossover strategy
news_aware_momentum      daily      YES      Momentum with news correlation
rsi_mean_reversion       weekly     YES      RSI mean reversion strategy
```

### `evaluate` - Evaluate a Strategy

Evaluates a strategy for specified symbols.

**Usage**:
```bash
vinu-strategy evaluate STRATEGY [TICKERS...] [OPTIONS]
```

**Arguments**:
- `STRATEGY` - Strategy name (required)
- `TICKERS` - Symbol(s) to evaluate (optional, uses strategy universe if not specified)

**Options**:
- `--json` - Output full JSON
- `--trace` - Show rule trace (which rules fired/not-fired)

**Examples**:

**Basic evaluation**:
```bash
vinu-strategy evaluate ma_crossover AAPL MSFT GOOGL
```

**Output**:
```
Strategy: ma_crossover
Run ID:   ma_crossover_20260706_143022
Time:     2026-07-06T14:30:22.123456

Symbol       Weight     Signal    
------------------------------------
AAPL         0.2500     0.1234    
MSFT         0.2500     0.0987    
GOOGL        0.2500     0.0456    
```

**With trace**:
```bash
vinu-strategy evaluate ma_crossover AAPL --trace
```

**Output**:
```
Strategy: ma_crossover
Run ID:   ma_crossover_20260706_143022
Time:     2026-07-06T14:30:22.123456

Symbol       Weight     Signal    
------------------------------------
AAPL         0.2500     0.1234    

Rule Trace:
============================================================

AAPL:
  + SMA_9
    features.SMA_9 gt SMA_21 -> 175.50 > 172.30 (true)
    -> action: weight_add(0.05), weight_after=0.30
```

**Full JSON**:
```bash
vinu-strategy evaluate ma_crossover AAPL --json
```

**Output**:
```json
{
  "strategy_name": "ma_crossover",
  "run_id": "ma_crossover_20260706_143022",
  "timestamp": "2026-07-06T14:30:22.123456",
  "weights": [
    {"symbol": "AAPL", "weight": 0.25, "signal_value": 0.1234}
  ],
  "metadata": {
    "symbol_count": 1,
    "weights": {"AAPL": 0.25}
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

### `schedule` - Run Periodic Evaluation

Runs periodic evaluation scheduler for all registered strategies.

**Usage**:
```bash
vinu-strategy schedule
```

**Behavior**:
- Lists all registered strategies
- Calculates evaluation intervals from schedule field
- Runs evaluations at specified intervals
- Logs all evaluations

**Example**:
```bash
vinu-strategy schedule
```

**Output**:
```
Scheduling 3 strategies. Press Ctrl+C to stop.

[2026-07-06T14:30:22] Evaluating 'ma_crossover'...
  - 3 weights, run_id=ma_crossover_20260706_143022

[2026-07-06T15:30:22] Evaluating 'ma_crossover'...
  - 3 weights, run_id=ma_crossover_20260706_153022

[2026-07-07T00:00:00] Evaluating 'rsi_mean_reversion'...
  - 5 weights, run_id=rsi_mean_reversion_20260707_000000
```

**Note**: Schedule field is parsed but automatic scheduling is not yet fully implemented.

### `reload` - Reload Strategy YAML Files

Reloads strategy YAML files from the strategies directory.

**Usage**:
```bash
vinu-strategy reload
```

**Example**:
```bash
vinu-strategy reload
```

**Output**:
```
Reloaded 3 strategies:
  - ma_crossover
  - news_aware_momentum
  - rsi_mean_reversion
```

**Use Case**: After adding or modifying strategy YAML files.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Strategy not found |
| 3 | Configuration error |
| 4 | API connection error |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FEATURES_API_URL` | vinu-features API URL | - |
| `CORRELATION_API_URL` | vinu-correlation API URL | - |
| `HOST` | Server host | 0.0.0.0 |
| `PORT` | Server port | 8000 |
| `DATA_ROOT` | Data directory | ./data |
| `STRATEGIES_DIR` | Strategies directory | ./strategies |

## Logging

**Log level**: WARNING (default)

**Log output**:
- Strategy loading
- Feature/correlation fetches
- Pipeline execution
- Storage operations

**Debug mode**: Not yet implemented (planned for v3).

## Examples

### Evaluate Multiple Symbols

```bash
vinu-strategy evaluate ma_crossover AAPL MSFT GOOGL AMZN META
```

### Evaluate with JSON Output

```bash
vinu-strategy evaluate news_aware_momentum --json > results.json
```

### Evaluate with Trace

```bash
vinu-strategy evaluate rsi_mean_reversion AAPL --trace
```

### Start Server

```bash
vinu-strategy serve --host 0.0.0.0 --port 8000
```

### List Strategies

```bash
vinu-strategy list
```

### Reload After Changes

```bash
# Modify strategy YAML
vim strategies/ma_crossover.yaml

# Reload
vinu-strategy reload

# Test
vinu-strategy evaluate ma_crossover AAPL
```

## Next Steps

- [HTTP API Reference](http-api.md)
- [Python API Reference](python-api.md)
- [Strategy Authoring](../strategy-authoring/yaml-schema.md)