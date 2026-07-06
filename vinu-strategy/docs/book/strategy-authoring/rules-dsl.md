# Rules DSL

## Overview

The Rules DSL (Domain Specific Language) allows you to implement complex trading logic through declarative rules.

## Rule Structure

```yaml
rules:
  - name: rule_name
    when:
      - {source: features, key: field, operator: value}
      - {source: correlation, key: field, operator: value}
    then: {action: action_type, value: number}
```

## Condition Structure

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | **Yes** | Data source (`features` or `correlation`) |
| `key` | string | **Yes** | Field name to evaluate |
| `operator` | string | **Yes** | Comparison operator |
| `value` | any | **Yes** | Comparison value |

### Sources

#### `features`

Technical indicators from vinu-features API.

**Examples**:
```yaml
{source: features, key: RSI_14, lt: 30}
{source: features, key: sma_9, gt: sma_21}
{source: features, key: momentum_20, gte: 0.0}
```

#### `correlation`

Correlation data from vinu-correlation API.

**Examples**:
```yaml
{source: correlation, key: high_impact_bullish_events, gt: 1}
{source: correlation, key: granger_causes_prices, eq: true}
{source: correlation, key: news_return_corr, gt: 0.4}
```

## Operators

### Comparison Operators

| Operator | Meaning | Example | Data Types |
|----------|---------|---------|------------|
| `eq` | equals | `{key: "status", eq: "active"}` | all |
| `neq` | not equals | `{key: "status", neq: "closed"}` | all |
| `gt` | greater than | `{key: "RSI_14", gt: 70}` | numeric |
| `gte` | greater or equal | `{key: "weight", gte: 0.25}` | numeric |
| `lt` | less than | `{key: "RSI_14", lt: 30}` | numeric |
| `lte` | less or equal | `{key: "weight", lte: 0.25}` | numeric |

### List Operators

| Operator | Meaning | Example | Data Types |
|----------|---------|---------|------------|
| `in` | in list | `{key: "sector", in: ["Tech", "Healthcare"]}` | any |
| `between` | between (inclusive) | `{key: "adx_14", between: [20, 40]}` | numeric |

### Operator Examples

```yaml
# Equality
{source: features, key: granger_causes_prices, eq: true}
{source: features, key: status, eq: "active"}

# Inequality
{source: features, key: status, neq: "closed"}

# Greater than
{source: features, key: RSI_14, gt: 70}
{source: features, key: momentum_20, gt: 0.0}

# Greater or equal
{source: features, key: weight, gte: 0.25}
{source: features, key: adx_14, gte: 25}

# Less than
{source: features, key: RSI_14, lt: 30}
{source: features, key: drawdown_count, lt: 2}

# Less or equal
{source: features, key: weight, lte: 0.25}

# In list
{source: features, key: sector, in: ["Tech", "Healthcare", "Finance"]}

# Between
{source: features, key: adx_14, between: [20, 40]}
{source: features, key: RSI_14, between: [30, 70]}
```

## Actions

### Action Types

| Action | Effect | Example | Use Case |
|--------|--------|---------|----------|
| `weight_add` | `current += value` | `{action: weight_add, value: 0.05}` | Boost weight on bullish signal |
| `weight_subtract` | `current -= value` | `{action: weight_subtract, value: 0.05}` | Reduce weight on caution signal |
| `weight_multiply` | `current *= value` | `{action: weight_multiply, value: 1.20}` | Scale weight by factor |
| `weight_set` | `current = value` | `{action: weight_set, value: 0.0}` | Force specific weight |

### Action Examples

```yaml
# Add 0.05 to weight
then: {action: weight_add, value: 0.05}

# Subtract 0.05 from weight
then: {action: weight_subtract, value: 0.05}

# Multiply weight by 1.20 (20% increase)
then: {action: weight_multiply, value: 1.20}

# Set weight to 0.0 (go to cash)
then: {action: weight_set, value: 0.0}

# Set weight to 0.15 (fixed position)
then: {action: weight_set, value: 0.15}
```

## Rule Evaluation

### AND Logic

All conditions in `when` must be true for the rule to fire.

```yaml
rules:
  - name: strong_bullish
    when:
      - {source: features, key: RSI_14, lt: 30}      # Oversold
      - {source: features, key: momentum_20, gt: 0}  # Positive momentum
      - {source: correlation, key: granger_causes_prices, eq: true}  # News confirms
    then: {action: weight_add, value: 0.10}
```

**Evaluation**:
1. Check RSI_14 lt 30: **true**
2. Check momentum_20 gt 0: **true**
3. Check granger_causes_prices eq true: **true**
4. All true: **Rule fires**

### Sequential Evaluation

Rules are evaluated **sequentially** per symbol. Later rules can override earlier ones.

```yaml
rules:
  - name: base_position
    when:
      - {source: features, key: momentum_20, gt: 0}
    then: {action: weight_add, value: 0.10}
  
  - name: reduce_on_overbought
    when:
      - {source: features, key: RSI_14, gt: 70}
    then: {action: weight_subtract, value: 0.05}
```

**Order matters**: If both conditions are true, both rules fire in order.

## Complete Examples

### Example 1: RSI Mean Reversion

```yaml
timing:
  method: rules
  rules:
    - name: oversold_buy
      when:
        - {source: features, key: RSI_14, lt: 30}
      then: {action: weight_add, value: 0.10}
    
    - name: overbought_sell
      when:
        - {source: features, key: RSI_14, gt: 70}
      then: {action: weight_set, value: 0.0}
    
    - name: neutral_hold
      when:
        - {source: features, key: RSI_14, between: [30, 70]}
      then: {action: weight_multiply, value: 1.0}
```

### Example 2: News-Aware Momentum

```yaml
timing:
  method: rules
  rules:
    - name: news_bullish_boost
      when:
        - {source: correlation, key: high_impact_bullish_events, gt: 1}
        - {source: correlation, key: granger_causes_prices, eq: true}
        - {source: features, key: adx_14, gt: 25}
      then: {action: weight_multiply, value: 1.20}
    
    - name: drawdown_cash
      when:
        - {source: correlation, key: drawdown_count, gt: 1}
      then: {action: weight_set, value: 0.0}
```

### Example 3: Multi-Condition Entry

```yaml
timing:
  method: rules
  rules:
    - name: ma_crossover_entry
      when:
        - {source: features, key: sma_9, gt: sma_21}
        - {source: features, key: volume_ratio_20, gt: 1.5}
      then: {action: weight_add, value: 0.05}
    
    - name: stop_loss
      when:
        - {source: features, key: daily_return, lt: -0.05}
      then: {action: weight_set, value: 0.0}
```

### Example 4: Sector Rotation

```yaml
timing:
  method: rules
  rules:
    - name: tech_boost
      when:
        - {source: features, key: sector, in: ["Tech", "Software"]}
        - {source: features, key: momentum_20, gt: 0.1}
      then: {action: weight_multiply, value: 1.30}
    
    - name: defensive_reduce
      when:
        - {source: features, key: sector, in: ["Utilities", "Consumer"]}
        - {source: features, key: adx_14, lt: 20}
      then: {action: weight_subtract, value: 0.05}
```

## Debugging Rules

### Enable Trace

```bash
vinu-strategy evaluate ma_crossover AAPL --trace
```

### Trace Output

```
Rule Trace:
============================================================

AAPL:
  + RSI_14
    features.RSI_14 lt 30 -> 45.2 >= 30 (false)
  - SMA_9
    features.SMA_9 gt SMA_21 -> 175.50 > 172.30 (true)
    -> action: weight_add(0.05), weight_after=0.30

MSFT:
  + RSI_14
    features.RSI_14 lt 30 -> 25.1 >= 30 (false)
    -> rule did not fire
```

## Best Practices

### 1. Use Descriptive Names

```yaml
# Good
name: oversold_buy_signal

# Bad
name: rule1
```

### 2. Keep Rules Simple

```yaml
# Good - single condition
when:
  - {source: features, key: RSI_14, lt: 30}

# Bad - too complex
when:
  - {source: features, key: RSI_14, lt: 30}
  - {source: features, key: sma_9, gt: sma_21}
  - {source: features, key: volume_ratio_20, gt: 1.5}
  - {source: correlation, key: high_impact_bullish_events, gt: 1}
  - {source: correlation, key: granger_causes_prices, eq: true}
```

### 3. Order Rules Carefully

```yaml
# Good - specific before general
rules:
  - name: stop_loss  # Specific condition
    when:
      - {source: features, key: daily_return, lt: -0.05}
    then: {action: weight_set, value: 0.0}
  
  - name: momentum_boost  # General condition
    when:
      - {source: features, key: momentum_20, gt: 0}
    then: {action: weight_add, value: 0.05}
```

### 4. Test with Trace

Always test rules with `--trace` flag to verify evaluation.

## Common Patterns

### Trend Following

```yaml
rules:
  - name: trend_long
    when:
      - {source: features, key: sma_9, gt: sma_21}
      - {source: features, key: adx_14, gt: 25}
    then: {action: weight_add, value: 0.05}
  
  - name: trend_exit
    when:
      - {source: features, key: sma_9, lt: sma_21}
    then: {action: weight_set, value: 0.0}
```

### Mean Reversion

```yaml
rules:
  - name: oversold_buy
    when:
      - {source: features, key: RSI_14, lt: 30}
    then: {action: weight_add, value: 0.10}
  
  - name: overbought_sell
    when:
      - {source: features, key: RSI_14, gt: 70}
    then: {action: weight_set, value: 0.0}
```

### Volume Confirmation

```yaml
rules:
  - name: volume_breakout
    when:
      - {source: features, key: volume_ratio_20, gt: 2.0}
      - {source: features, key: daily_return, gt: 0.03}
    then: {action: weight_multiply, value: 1.50}
```

## Next Steps

- [Strategy Examples](examples.md)
- [API Reference](../api-reference/cli.md)
- [Testing Guide](../testing/test-guide.md)