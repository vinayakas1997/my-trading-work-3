# Pipeline Design

## Overview

The **WeightPipeline** is the core processing engine that transforms raw signals into optimized portfolio weights. It consists of 4 sequential stages, each with configurable methods.

## Pipeline Stages

```
Universe Symbols
       |
       v
+-------------+
|  Selection  |  -> Filter to candidates
+-------------+
       |
       v
+--------------+
|  Allocation  |  -> Assign initial weights
+--------------+
       |
       v
+----------+
|  Timing  |  -> Adjust weights via rules
+----------+
       |
       v
+-------+
|  Risk |  -> Normalize within constraints
+-------+
       |
       v
Final Portfolio Weights
```

## Stage 1: Selection

**Purpose**: Filter the universe to a manageable set of candidates.

**Methods**:

### `all`

Passes all symbols through unchanged.

```yaml
selection:
  method: all
```

**Use Case**: When you want to evaluate all symbols in the universe.

### `threshold`

Keeps symbols where a signal meets or exceeds a minimum threshold.

```yaml
selection:
  method: threshold
  on: RSI_14
  min: 30
```

**Params**:
- `on` (str): Feature field name to evaluate
- `min` (float): Minimum value to include

**Logic**:
```python
def select_threshold(universe, signals, field, min_val):
    return [sym for sym in universe 
            if signals[sym].get(field, 0) >= min_val]
```

**Use Case**: Select only oversold stocks (RSI<30) or momentum leaders (momentum>0).

### `top_n`

Keeps the top N symbols by signal value.

```yaml
selection:
  method: top_n
  n: 5
  on: momentum_20
```

**Params**:
- `n` (int): Number of top symbols to keep
- `on` (str): Feature field name for ranking

**Logic**:
```python
def select_top_n(universe, signals, field, n):
    ranked = sorted(universe, 
                    key=lambda s: signals[s].get(field, 0), 
                    reverse=True)
    return ranked[:n]
```

**Use Case**: Allocate to top 5 momentum leaders.

## Stage 2: Allocation

**Purpose**: Assign initial weights to selected symbols.

**Methods**:

### `equal`

Equal weight allocation (1/N per symbol).

```yaml
allocation:
  method: equal
```

**Logic**:
```python
def allocate_equal(candidates):
    weight = 1.0 / len(candidates) if candidates else 0.0
    return {sym: weight for sym in candidates}
```

**Use Case**: Simple diversification, baseline portfolio.

### `signal_scaled`

Weight proportional to signal strength.

```yaml
allocation:
  method: signal_scaled
  signal: RSI_14
```

**Params**:
- `signal` (str, optional): Signal expression or field name

**Logic**:
```python
def allocate_signal_scaled(candidates, signals, signal_expr=None):
    if signal_expr:
        # Evaluate expression per symbol
        values = {sym: evaluate_expression(signal_expr, signals[sym]) 
                  for sym in candidates}
    else:
        # Use aggregated signal
        values = {sym: signals[sym].get("signal", 0) 
                  for sym in candidates}
    
    # Normalize to sum to 1
    total = sum(abs(v) for v in values.values())
    if total == 0:
        return {sym: 1/len(candidates) for sym in candidates}
    
    return {sym: v/total for sym, v in values.items()}
```

**Use Case**: Allocate more to stronger signals, preserve signal direction.

## Stage 3: Timing

**Purpose**: Adjust weights based on rule-based conditions.

**Methods**:

### `none`

No timing adjustments.

```yaml
timing:
  method: none
```

**Use Case**: When timing is handled by selection/allocation.

### `rules`

Apply rules to adjust weights.

```yaml
timing:
  method: rules
  rules:
    - name: oversold_boost
      when:
        - {source: features, key: RSI_14, lt: 30}
      then: {action: weight_add, value: 0.05}
    - name: overbought_reduce
      when:
        - {source: features, key: RSI_14, gt: 70}
      then: {action: weight_subtract, value: 0.05}
```

**Rule Structure**:
- `name` (str): Unique rule identifier
- `when` (list): Conditions (all must be true)
- `then` (dict): Action to take

**Condition Sources**:
- `features`: Technical indicators from vinu-features
- `correlation`: Correlation data from vinu-correlation

**Operators**: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `between`

**Actions**:
- `weight_add`: Add value to current weight
- `weight_subtract`: Subtract value from current weight
- `weight_multiply`: Multiply weight by value
- `weight_set`: Set weight to specific value

**Use Case**: Implement complex trading logic like "boost weight when oversold with high volume".

## Stage 4: Risk

**Purpose**: Normalize weights within risk constraints.

**Methods**:

### `normalize`

Cap individual weights and reserve cash floor.

```yaml
risk:
  method: normalize
  max_weight: 0.25
  cash_floor: 0.10
  max_short_weight: 0.10
  allow_short: true
```

**Params**:
- `max_weight` (float, default 0.25): Maximum long position
- `cash_floor` (float, default 0.10): Minimum cash reserve
- `max_short_weight` (float, default max_weight): Maximum short position
- `allow_short` (bool, default true): Whether to allow shorts

**Logic**:
1. Split longs and shorts
2. Cap each at their respective limits
3. Scale proportionally if total exposure exceeds `1 - cash_floor`
4. Return normalized weights

**Example**:
```python
# Input: {"AAPL": 0.50, "MSFT": -0.30}
# max_weight=0.25, cash_floor=0.10
# Output: {"AAPL": 0.45, "MSFT": -0.45}
# Total gross = 0.90, net = 0.00, cash = 0.10
```

### `none`

No risk normalization.

```yaml
risk:
  method: none
```

**Use Case**: When allocation already respects constraints.

## Pipeline Execution Flow

```python
def run_pipeline(config, universe, feature_signals, correlation_signals, params):
    # Stage 1: Selection
    candidates = run_selection(
        method=config.pipeline.selection.method,
        universe=universe,
        signals=feature_signals,
        params=config.pipeline.selection.params
    )
    
    # Stage 2: Allocation
    weights = run_allocation(
        method=config.pipeline.allocation.method,
        candidates=candidates,
        signals=feature_signals,
        params=config.pipeline.allocation.params,
        signal_context=feature_signals
    )
    
    # Stage 3: Timing
    weights = run_timing(
        method=config.pipeline.timing.method,
        weights=weights,
        candidates=candidates,
        signals=feature_signals,
        rules=config.pipeline.timing.rules
    )
    
    # Stage 4: Risk
    weights = run_risk(
        method=config.pipeline.risk.method,
        weights=weights,
        params=config.pipeline.risk.params
    )
    
    return weights
```

## Best Practices

### 1. Selection Efficiency

- Use `threshold` to reduce universe size before allocation
- Avoid `top_n` with very large n (performance impact)

### 2. Allocation Clarity

- Use `signal_scaled` for directional strategies
- Use `equal` for diversification

### 3. Timing Rules

- Order rules carefully (first match wins for same symbol)
- Use descriptive names for rules
- Test with `--trace` flag

### 4. Risk Management

- Set `max_weight` based on position concentration risk
- Set `cash_floor` based on liquidity needs
- Use `allow_short: false` for long-only portfolios

## Debugging

Enable rule trace:
```bash
vinu-strategy evaluate ma_crossover AAPL --trace
```

Output shows:
- Which rules fired
- Condition evaluations
- Weight changes per rule

## Custom Methods

Extend pipeline with custom methods:

```python
# Register custom selection method
from vinu_strategy.engine.selection import SELECTION_METHODS
SELECTION_METHODS["custom"] = custom_selection_func
```

Custom methods must accept:
- `universe`: List of symbols
- `signals`: Dict of feature signals
- `params`: Method parameters

Return: List of selected symbols