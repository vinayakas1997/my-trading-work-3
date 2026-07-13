# Pipeline Methods

## Overview

This document describes all available pipeline methods for each stage of the WeightPipeline.

## Selection Methods

### `all`

**Description**: Pass all symbols through unchanged.

**Params**: None

**Use Case**: When you want to evaluate the entire universe.

**Example**:
```yaml
selection:
  method: all
```

**Logic**:
```python
def select_all(universe, signals, params):
    return list(universe)
```

### `threshold`

**Description**: Filter symbols by signal threshold.

**Params**:
- `on` (str, required): Feature field to evaluate
- `min` (float, required): Minimum value to include

**Use Case**: Select only oversold stocks or momentum leaders.

**Example**:
```yaml
selection:
  method: threshold
  on: RSI_14
  min: 30
```

**Logic**:
```python
def select_threshold(universe, signals, field, min_val):
    return [
        sym for sym in universe
        if signals[sym].get(field, 0) >= min_val
    ]
```

**Examples**:
```yaml
# Select oversold stocks
selection:
  method: threshold
  on: RSI_14
  min: 30

# Select positive momentum
selection:
  method: threshold
  on: momentum_20
  min: 0.0

# Select strong trend
selection:
  method: threshold
  on: adx_14
  min: 25
```

### `top_n`

**Description**: Keep top N symbols by signal value.

**Params**:
- `on` (str, required): Feature field for ranking
- `n` (int, required): Number of top symbols to keep

**Use Case**: Allocate to top performers only.

**Example**:
```yaml
selection:
  method: top_n
  on: momentum_20
  n: 5
```

**Logic**:
```python
def select_top_n(universe, signals, field, n):
    ranked = sorted(
        universe,
        key=lambda s: signals[s].get(field, 0),
        reverse=True
    )
    return ranked[:n]
```

**Examples**:
```yaml
# Top 5 momentum leaders
selection:
  method: top_n
  on: momentum_20
  n: 5

# Top 3 RSI oversold
selection:
  method: top_n
  on: RSI_14
  n: 3
```

## Allocation Methods

### `equal`

**Description**: Equal weight allocation (1/N per symbol).

**Params**: None

**Use Case**: Simple diversification, baseline portfolio.

**Example**:
```yaml
allocation:
  method: equal
```

**Logic**:
```python
def allocate_equal(candidates, signals, params):
    if not candidates:
        return {}
    weight = 1.0 / len(candidates)
    return {sym: weight for sym in candidates}
```

**Output**:
```python
{"AAPL": 0.33, "MSFT": 0.33, "GOOGL": 0.34}
```

### `signal_scaled`

**Description**: Weight proportional to signal strength.

**Params**:
- `signal` (str, optional): Signal expression or field name

**Use Case**: Allocate more to stronger signals, preserve signal direction.

**Example**:
```yaml
allocation:
  method: signal_scaled
  signal: momentum_20
```

**Logic**:
```python
def allocate_signal_scaled(candidates, signals, signal_expr, signal_context):
    if signal_expr:
        # Evaluate expression per symbol
        values = {
            sym: evaluate_expression(signal_expr, signals[sym])
            for sym in candidates
        }
    else:
        # Use aggregated signal
        values = {
            sym: signals[sym].get("signal", 0)
            for sym in candidates
        }
    
    # Normalize to sum to 1
    total = sum(abs(v) for v in values.values())
    if total == 0:
        return {sym: 1/len(candidates) for sym in candidates}
    
    return {sym: v/total for sym, v in values.items()}
```

**Expression Support**:
```yaml
# Simple field
allocation:
  method: signal_scaled
  signal: RSI_14

# Expression
allocation:
  method: signal_scaled
  signal: "sma_9 / sma_21 - 1"

# Complex expression
allocation:
  method: signal_scaled
  signal: "(momentum_20 + adx_14 / 100) / 2"
```

**Output**:
```python
# Input: {"AAPL": 0.1, "MSFT": -0.05, "GOOGL": 0.15}
# Output: {"AAPL": 0.25, "MSFT": -0.125, "GOOGL": 0.375}
# Total absolute weight = 0.75, normalized to 1.0
```

## Timing Methods

### `none`

**Description**: No timing adjustments.

**Params**: None

**Use Case**: When timing is handled by selection/allocation.

**Example**:
```yaml
timing:
  method: none
```

**Logic**:
```python
def timing_none(weights, candidates, signals, rules):
    return weights
```

### `rules`

**Description**: Apply rule-based adjustments.

**Params**:
- `rules` (list[dict], required): List of rule definitions

**Use Case**: Implement complex trading logic.

**Example**:
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
```yaml
rules:
  - name: unique_name
    when:
      - {source: features, key: field, operator: value}
      - {source: correlation, key: field, operator: value}
    then: {action: action_type, value: number}
```

**Actions**:
- `weight_add`: Add value to current weight
- `weight_subtract`: Subtract value from current weight
- `weight_multiply`: Multiply weight by value
- `weight_set`: Set weight to specific value

**Logic**:
```python
def timing_rules(weights, candidates, signals, rules):
    result = dict(weights)
    for rule in rules:
        for sym in candidates:
            if evaluate_conditions(sym, signals[sym], rule["when"]):
                current = result.get(sym, 0)
                action = rule["then"]["action"]
                value = rule["then"]["value"]
                
                if action == "weight_add":
                    result[sym] = current + value
                elif action == "weight_subtract":
                    result[sym] = current - value
                elif action == "weight_multiply":
                    result[sym] = current * value
                elif action == "weight_set":
                    result[sym] = value
    return result
```

## Risk Methods

### `normalize`

**Description**: Cap individual weights and reserve cash floor.

**Params**:
- `max_weight` (float, default 0.25): Maximum long position
- `cash_floor` (float, default 0.10): Minimum cash reserve
- `max_short_weight` (float, default max_weight): Maximum short position
- `allow_short` (bool, default true): Whether to allow shorts

**Use Case**: Enforce position limits and cash requirements.

**Example**:
```yaml
risk:
  method: normalize
  max_weight: 0.25
  cash_floor: 0.10
  max_short_weight: 0.10
  allow_short: true
```

**Logic**:
```python
def risk_normalize(weights, params):
    max_w = params.get("max_weight", 0.25)
    max_short_w = params.get("max_short_weight", max_w)
    cash_floor = params.get("cash_floor", 0.10)
    allow_short = params.get("allow_short", True)
    
    if not allow_short:
        return _risk_normalize_long_only(weights, max_w, cash_floor)
    
    return _risk_normalize_with_shorts(weights, max_w, max_short_w, cash_floor)
```

**Long-Only**:
```python
def _risk_normalize_long_only(weights, max_w, cash_floor):
    # Cap longs at max_w
    result = {sym: min(w, max_w) for sym, w in weights.items() if w > 0}
    
    # Scale if total > 1 - cash_floor
    total = sum(result.values())
    if total > (1.0 - cash_floor):
        scale = (1.0 - cash_floor) / total
        result = {sym: w * scale for sym, w in result.items()}
    
    return result
```

**With Shorts**:
```python
def _risk_normalize_with_shorts(weights, max_w, max_short_w, cash_floor):
    # Split longs and shorts
    longs = {sym: min(w, max_w) for sym, w in weights.items() if w >= 0}
    shorts = {sym: max(w, -max_short_w) for sym, w in weights.items() if w > 0}
    
    # Scale if gross > 1 - cash_floor
    gross = sum(longs.values()) + abs(sum(shorts.values()))
    limit = 1.0 - cash_floor
    if gross > limit:
        scale = limit / gross
        longs = {sym: w * scale for sym, w in longs.items()}
        shorts = {sym: w * scale for sym, w in shorts.items()}
    
    # Combine
    result = {}
    result.update(longs)
    result.update(shorts)
    return result
```

**Examples**:

**Long-Only**:
```yaml
risk:
  method: normalize
  max_weight: 0.25
  cash_floor: 0.10
```

**With Shorts**:
```yaml
risk:
  method: normalize
  max_weight: 0.25
  max_short_weight: 0.10
  cash_floor: 0.10
  allow_short: true
```

### `none`

**Description**: No risk normalization.

**Params**: None

**Use Case**: When allocation already respects constraints.

**Example**:
```yaml
risk:
  method: none
```

**Logic**:
```python
def risk_none(weights, params):
    return dict(weights)
```

## Method Combinations

### Conservative Portfolio

```yaml
selection:
  method: threshold
  on: adx_14
  min: 25
allocation:
  method: equal
risk:
  method: normalize
  max_weight: 0.20
  cash_floor: 0.20
```

### Aggressive Momentum

```yaml
selection:
  method: top_n
  on: momentum_20
  n: 10
allocation:
  method: signal_scaled
  signal: momentum_20
risk:
  method: normalize
  max_weight: 0.30
  cash_floor: 0.05
```

### Mean Reversion

```yaml
selection:
  method: threshold
  on: RSI_14
  min: 0
  max: 100
allocation:
  method: signal_scaled
  signal: "100 - RSI_14"
timing:
  method: rules
  rules:
    - name: oversold
      when:
        - {source: features, key: RSI_14, lt: 30}
      then: {action: weight_add, value: 0.05}
risk:
  method: normalize
  max_weight: 0.25
  cash_floor: 0.10
```

## Custom Methods

### Registering Custom Methods

```python
# In your code
from vinu_strategy.engine.selection import SELECTION_METHODS

def custom_selection(universe, signals, params):
    # Custom logic
    return [sym for sym in universe if should_include(sym, signals[sym])]

SELECTION_METHODS["custom"] = custom_selection
```

### Custom Method Signature

All custom methods must accept:
- `universe` (list[str]): List of all symbols
- `signals` (dict[str, dict]): Feature signals per symbol
- `params` (dict): Method parameters

**Selection/Allocation**: Return list of symbols or dict of weights
**Timing/Risk**: Return dict of weights

## Next Steps

- [Rules DSL](rules-dsl.md)
- [Strategy Examples](examples.md)
- [API Reference](../api-reference/cli.md)