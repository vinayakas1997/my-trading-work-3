# YAML Schema

## Complete Schema Reference

This document describes the complete YAML schema for vinu-strategy configurations.

## Full Example

```yaml
name: news_aware_momentum
description: "Momentum strategy with news correlation"
schedule: daily
features_required:
  - momentum_20
  - adx_14
  - volume_ratio_20
correlation_required:
  - impact
  - granger
  - drawdown
universe:
  source: inline
  inline:
    - AAPL
    - MSFT
    - GOOGL
    - AMZN
    - META
pipeline:
  selection:
    method: threshold
    on: momentum_20
    min: 0.0
  allocation:
    method: signal_scaled
    signal: momentum_20
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
  risk:
    method: normalize
    max_weight: 0.25
    cash_floor: 0.10
    max_short_weight: 0.10
    allow_short: true
```

## Schema Definition

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Unique strategy identifier |
| `description` | string | No | Human-readable description |
| `schedule` | string | No | Rebalance frequency (`daily` \| `weekly`) |
| `features_required` | list[string] | No | List of feature indicators |
| `correlation_required` | list[string] | No | List of correlation fields |
| `universe` | object | No | Universe specification |
| `pipeline` | object | **Yes** | Pipeline configuration |

### Universe Specification

```yaml
universe:
  source: "inline"  # or "watchlist"
  inline:           # required if source="inline"
    - AAPL
    - MSFT
    - GOOGL
```

**Options**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | No | Source type (`inline` \| `watchlist`) |
| `inline` | list[string] | Conditional | Symbol list if source=inline |
| `path` | string | Conditional | Watchlist file path if source=watchlist |

**Default**: If not specified, uses `["AAPL", "MSFT", "GOOGL", "AMZN", "META"]`

### Pipeline Specification

```yaml
pipeline:
  selection:
    method: all
  allocation:
    method: equal
  timing:
    method: none
  risk:
    method: normalize
```

## Selection Configuration

### Method: `all`

```yaml
selection:
  method: all
```

**Behavior**: Passes all symbols through unchanged.

### Method: `threshold`

```yaml
selection:
  method: threshold
  on: momentum_20
  min: 0.0
```

**Params**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `on` | string | **Yes** | Feature field to evaluate |
| `min` | float | **Yes** | Minimum value to include |

**Logic**:
```
Include symbol if: signal[sym][on] >= min
```

### Method: `top_n`

```yaml
selection:
  method: top_n
  on: momentum_20
  n: 5
```

**Params**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `on` | string | **Yes** | Feature field for ranking |
| `n` | integer | **Yes** | Number of top symbols to keep |

**Logic**:
```
Rank symbols by signal[sym][on] descending
Return top n symbols
```

## Allocation Configuration

### Method: `equal`

```yaml
allocation:
  method: equal
```

**Behavior**: Equal weight allocation (1/N per symbol).

### Method: `signal_scaled`

```yaml
allocation:
  method: signal_scaled
  signal: momentum_20
```

**Params**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `signal` | string | No | Signal expression or field name |

**Behavior**:
- If `signal` specified: Weight proportional to signal value
- If no `signal`: Uses aggregated signal from features

**Expression Support**:
```yaml
signal: "sma_9 / sma_21 - 1"
signal: "rsi_14 / 100"
signal: "momentum_20 * 0.5"
```

## Timing Configuration

### Method: `none`

```yaml
timing:
  method: none
```

**Behavior**: No timing adjustments.

### Method: `rules`

```yaml
timing:
  method: rules
  rules:
    - name: rule_name
      when:
        - {source: features, key: RSI_14, lt: 30}
        - {source: features, key: volume_ratio_20, gt: 1.5}
      then: {action: weight_add, value: 0.05}
```

**Rule Structure**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **Yes** | Unique rule identifier |
| `when` | list[object] | **Yes** | Conditions (all must be true) |
| `then` | object | **Yes** | Action to take |

### Condition Structure

```yaml
{
  source: "features",  # or "correlation"
  key: "RSI_14",
  lt: 30
}
```

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | **Yes** | Data source (`features` \| `correlation`) |
| `key` | string | **Yes** | Field name to evaluate |
| `operator` | string | **Yes** | Comparison operator |

**Operators**:

| Operator | Meaning | Example |
|----------|---------|---------|
| `eq` | equals | `{key: "status", eq: "active"}` |
| `neq` | not equals | `{key: "status", neq: "closed"}` |
| `gt` | greater than | `{key: "RSI_14", gt: 70}` |
| `gte` | greater or equal | `{key: "weight", gte: 0.25}` |
| `lt` | less than | `{key: "RSI_14", lt: 30}` |
| `lte` | less or equal | `{key: "weight", lte: 0.25}` |
| `in` | in list | `{key: "sector", in: ["Tech", "Healthcare"]}` |
| `between` | between (inclusive) | `{key: "adx_14", between: [20, 40]}` |

### Action Structure

```yaml
then: {action: weight_add, value: 0.05}
```

**Actions**:

| Action | Effect | Example |
|--------|--------|---------|
| `weight_add` | `current += value` | Add 0.05 to weight |
| `weight_subtract` | `current -= value` | Subtract 0.05 from weight |
| `weight_multiply` | `current *= value` | Multiply weight by 1.20 |
| `weight_set` | `current = value` | Set weight to 0.0 |

## Risk Configuration

### Method: `normalize`

```yaml
risk:
  method: normalize
  max_weight: 0.25
  cash_floor: 0.10
  max_short_weight: 0.10
  allow_short: true
```

**Params**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `max_weight` | float | 0.25 | Maximum long position |
| `cash_floor` | float | 0.10 | Minimum cash reserve |
| `max_short_weight` | float | max_weight | Maximum short position |
| `allow_short` | bool | true | Whether to allow shorts |

**Behavior**:
1. Split weights into longs and shorts
2. Cap longs at `max_weight`
3. Cap shorts at `-max_short_weight`
4. Scale proportionally if total exposure > `1 - cash_floor`
5. Return normalized weights

### Method: `none`

```yaml
risk:
  method: none
```

**Behavior**: Pass weights through unchanged.

## Feature Names

Feature names must match exactly from the [Feature Catalog](features-catalog.md).

**Examples**:
```yaml
features_required:
  - sma_9
  - sma_21
  - rsi_14
  - momentum_20
  - volume_ratio_20
```

**Case sensitivity**: Feature names are case-insensitive in evaluation.

## Correlation Fields

Correlation fields must match from the [Correlation Fields](correlation-fields.md).

**Examples**:
```yaml
correlation_required:
  - impact
  - granger
  - drawdown
```

## Schedule Values

| Value | Frequency |
|-------|-----------|
| `hourly` | Every hour |
| `daily` | Once per day |
| `weekly` | Once per week |
| `monthly` | Once per month |

**Note**: Schedule is parsed but not yet implemented in scheduler.

## Validation

### What Gets Validated

1. **YAML syntax**: `yaml.safe_load()` catches syntax errors
2. **Required fields**: `name` and `pipeline` must be present
3. **Method names**: Must match known methods
4. **Field names**: Must exist in feature/correlation catalogs

### What Doesn't Get Validated

1. **Typo in field names**: Silent fallback to defaults
2. **Invalid parameter values**: May cause runtime errors
3. **Non-existent features**: Returns 0.0 for missing features

### Best Practices

1. **Use `vinu-strategy reload`** after adding/changing YAML files
2. **Test with `--trace`** to verify rule evaluation
3. **Check logs** for warnings about unknown keys
4. **Validate features** against feature catalog

## Examples

### Simple Equal Weight

```yaml
name: equal_weight
description: "Equal weight portfolio"
pipeline:
  selection:
    method: all
  allocation:
    method: equal
  timing:
    method: none
  risk:
    method: normalize
```

### Momentum with Threshold

```yaml
name: momentum_threshold
description: "Momentum strategy with threshold"
features_required:
  - momentum_20
pipeline:
  selection:
    method: threshold
    on: momentum_20
    min: 0.0
  allocation:
    method: signal_scaled
    signal: momentum_20
  timing:
    method: none
  risk:
    method: normalize
```

### RSI Mean Reversion

```yaml
name: rsi_mean_reversion
description: "RSI mean reversion"
features_required:
  - rsi_14
pipeline:
  selection:
    method: all
  allocation:
    method: equal
  timing:
    method: rules
    rules:
      - name: oversold_buy
        when:
          - {source: features, key: rsi_14, lt: 30}
        then: {action: weight_add, value: 0.10}
      - name: overbought_sell
        when:
          - {source: features, key: rsi_14, gt: 70}
        then: {action: weight_set, value: 0.0}
  risk:
    method: normalize
```

## Migration from Old Format

### Old Format (Deprecated)

```yaml
name: ma_crossover
sma_fast: 9
sma_slow: 21
```

### New Format

```yaml
name: ma_crossover
features_required:
  - sma_9
  - sma_21
pipeline:
  selection:
    method: all
  allocation:
    method: signal_scaled
    signal: "sma_9 / sma_21 - 1"
  timing:
    method: none
  risk:
    method: normalize
```

## Next Steps

- [Feature Catalog](features-catalog.md)
- [Correlation Fields](correlation-fields.md)
- [Pipeline Methods](pipeline-methods.md)
- [Rules DSL](rules-dsl.md)
- [Examples](examples.md)