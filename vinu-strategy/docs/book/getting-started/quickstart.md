# Quick Start

This guide will have you running your first trading strategy in under 5 minutes.

## Step 1: Install and Configure

```bash
# Install the package
pip install vinu-strategy

# Create a working directory
mkdir ~/vinu-work
cd ~/vinu-work

# Create .env file
cat > .env<<EOF
FEATURES_API_URL=http://localhost:8000
CORRELATION_API_URL=http://localhost:8001
STRATEGIES_DIR=./strategies
DATA_ROOT=./data
EOF
```

## Step 2: Create Your First Strategy

Create a `strategies` directory and add a simple MA crossover strategy:

```bash
mkdir strategies
cat > strategies/ma_crossover.yaml<<EOF
name: ma_crossover
description: Simple 9/21 SMA crossover strategy
schedule: daily
features_required:
  - sma_9
  - sma_21
pipeline:
  selection:
    method: all
  allocation:
    method: signal_scaled
  timing:
    method: none
  risk:
    method: normalize
    max_weight: 0.25
    cash_floor: 0.10
EOF
```

## Step 3: Register the Strategy

```bash
vinu-strategy reload
```

Expected output:
```
Reloaded 1 strategies:
  - ma_crossover
```

## Step 4: List Strategies

```bash
vinu-strategy list
```

Expected output:
```
Name                     Schedule   Enabled  Description
--------------------------------------------------------------------------------
ma_crossover             daily      ✓        Simple 9/21 SMA crossover strategy
```

## Step 5: Evaluate the Strategy

Test with specific symbols:

```bash
vinu-strategy evaluate ma_crossover AAPL MSFT GOOGL
```

Expected output:
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

## Step 6: View Full JSON Output

```bash
vinu-strategy evaluate ma_crossover AAPL MSFT --json
```

## Step 7: Start the HTTP API Server

```bash
vinu-strategy serve
```

The server will start at `http://localhost:8000`. Access the web UI at the same URL.

## Step 8: Check Your Data

Weights are stored in `data/weights/` as Parquet files. Inspect them:

```python
import pandas as pd
import pyarrow.parquet as pq

# Read weight history
df = pq.read_table("data/weights/ma_crossover/2026.parquet").to_pandas()
print(df.head())
```

## Next Steps

- [Learn YAML Schema](../strategy-authoring/yaml-schema.md)
- [Explore Feature Catalog](../strategy-authoring/features-catalog.md)
- [Build Custom Strategies](../strategy-authoring/examples.md)
- [Read API Documentation](../api-reference/http-api.md)

## Common Patterns

### Equal Weight Portfolio

```yaml
allocation:
  method: equal
```

### Signal-Scaled Allocation

```yaml
allocation:
  method: signal_scaled
  signal: RSI_14
```

### Threshold Selection

```yaml
selection:
  method: threshold
  on: momentum_20
  min: 0.0
```

### Rule-Based Timing

```yaml
timing:
  method: rules
  rules:
    - name: bullish_boost
      when:
        - {source: features, key: RSI_14, lt: 30}
      then: {action: weight_add, value: 0.05}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Strategy not found` | Run `vinu-strategy reload` |
| `Empty universe` | Check your strategy's `universe.inline` list |
| `API connection error` | Verify `FEATURES_API_URL` and `CORRELATION_API_URL` |
| `No weights generated` | Check `--trace` flag for rule evaluation details |

## Summary

You've now:
1. Installed vinu-strategy
2. Created your first strategy YAML
3. Registered and evaluated the strategy
4. Started the HTTP API server

Continue building more complex strategies using the [Strategy Authoring Guide](../strategy-authoring/yaml-schema.md).