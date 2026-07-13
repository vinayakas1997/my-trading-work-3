# Correlation Fields

## Overview

This document describes all available correlation fields from **vinu-correlation** API that can be used in strategy rules and conditions.

## Correlation Sources

### 1. Impact Data

**Source**: `correlation.impact`

**Fields**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `high_impact_bullish_events` | int | # of bullish news with high price impact | 3 |
| `high_impact_bearish_events` | int | # of bearish news with high price impact | 1 |
| `avg_price_drop_30m` | float | Avg 30m price drop for bearish events | -0.023 |
| `event_count` | int | Total impact events | 4 |

**Example**:
```yaml
correlation_required:
  - impact
```

**Rule usage**:
```yaml
timing:
  rules:
    - name: news_boost
      when:
        - {source: correlation, key: high_impact_bullish_events, gt: 1}
      then: {action: weight_multiply, value: 1.20}
```

### 2. Granger Causality

**Source**: `correlation.granger`

**Fields**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `granger_p_value` | float | Granger causality p-value | 0.032 |
| `granger_causes_prices` | bool | Whether news Granger-causes prices at 95% CI | true |
| `best_lag_minutes` | int | Best predictive lag in minutes | 30 |
| `best_lag_correlation` | float | Correlation at best lag | 0.45 |

**Example**:
```yaml
correlation_required:
  - granger
```

**Rule usage**:
```yaml
timing:
  rules:
    - name: granger_confirmed
      when:
        - {source: correlation, key: granger_causes_prices, eq: true}
      then: {action: weight_add, value: 0.05}
```

### 3. Correlation Analysis

**Source**: `correlation.correlation`

**Fields**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `news_return_corr` | float | Pearson correlation (news volume vs returns) | 0.45 |
| `corr_p_value` | float | P-value of correlation | 0.021 |
| `sentiment_return_corr` | float | Correlation (sentiment vs returns) | 0.32 |

**Example**:
```yaml
correlation_required:
  - correlation
```

**Rule usage**:
```yaml
timing:
  rules:
    - name: strong_correlation
      when:
        - {source: correlation, key: news_return_corr, gt: 0.4}
      then: {action: weight_multiply, value: 1.15}
```

### 4. Drawdown Analysis

**Source**: `correlation.drawdown`

**Fields**:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `drawdown_count` | int | Number of significant drawdowns detected | 2 |
| `max_drawdown` | float | Maximum drawdown percentage | -0.15 |
| `drawdown_duration` | int | Duration of longest drawdown (bars) | 5 |

**Example**:
```yaml
correlation_required:
  - drawdown
```

**Rule usage**:
```yaml
timing:
  rules:
    - name: drawdown_cash
      when:
        - {source: correlation, key: drawdown_count, gt: 1}
      then: {action: weight_set, value: 0.0}
```

## Complete Example

```yaml
name: news_aware_momentum
description: "Momentum with news correlation"
features_required:
  - momentum_20
  - adx_14
correlation_required:
  - impact
  - granger
  - correlation
  - drawdown
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
```

## Flattening Behavior

Correlation data is **flattened** when passed to the pipeline:

**Input** (from API):
```json
{
  "impact": {
    "high_impact_bullish_events": 3,
    "high_impact_bearish_events": 1
  },
  "granger": {
    "granger_causes_prices": true,
    "granger_p_value": 0.032
  }
}
```

**Flattened** (for rules):
```python
{
  "high_impact_bullish_events": 3,
  "high_impact_bearish_events": 1,
  "granger_causes_prices": true,
  "granger_p_value": 0.032
}
```

**Rule access**: Use the flattened key directly:
```yaml
{source: correlation, key: high_impact_bullish_events, gt: 1}
```

## Data Types in Rules

### Integer Fields

| Field | Type | Example |
|-------|------|---------|
| `high_impact_bullish_events` | int | 3 |
| `high_impact_bearish_events` | int | 1 |
| `event_count` | int | 4 |
| `drawdown_count` | int | 2 |
| `best_lag_minutes` | int | 30 |

**Operators**: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between`

### Float Fields

| Field | Type | Example |
|-------|------|---------|
| `avg_price_drop_30m` | float | -0.023 |
| `granger_p_value` | float | 0.032 |
| `best_lag_correlation` | float | 0.45 |
| `news_return_corr` | float | 0.45 |
| `corr_p_value` | float | 0.021 |

**Operators**: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between`

### Boolean Fields

| Field | Type | Example |
|-------|------|---------|
| `granger_causes_prices` | bool | true |

**Operators**: `eq`, `neq`

## Best Practices

### 1. Request Only Needed Fields

```yaml
# Good - only request what you use
correlation_required:
  - impact

# Bad - request everything
correlation_required:
  - impact
  - granger
  - correlation
  - drawdown
```

### 2. Use Appropriate Thresholds

```yaml
# Good - meaningful thresholds
when:
  - {source: correlation, key: high_impact_bullish_events, gt: 1}

# Bad - arbitrary thresholds
when:
  - {source: correlation, key: high_impact_bullish_events, gt: 100}
```

### 3. Combine Multiple Signals

```yaml
# Good - multiple conditions
when:
  - {source: correlation, key: high_impact_bullish_events, gt: 1}
  - {source: correlation, key: granger_causes_prices, eq: true}
  - {source: features, key: adx_14, gt: 25}
```

### 4. Handle Missing Data

Missing correlation data returns empty dict. Rules with missing keys evaluate to false.

## API Endpoints

### Impact

```
GET /correlation/{symbol}/impact
```

**Response**:
```json
{
  "impact": {
    "high_impact_bullish_events": 3,
    "high_impact_bearish_events": 1,
    "avg_price_drop_30m": -0.023,
    "event_count": 4
  }
}
```

### Granger

```
GET /correlation/{symbol}/granger
```

**Response**:
```json
{
  "granger": {
    "granger_p_value": 0.032,
    "granger_causes_prices": true,
    "best_lag_minutes": 30,
    "best_lag_correlation": 0.45
  }
}
```

### Correlation

```
GET /correlation/{symbol}/correlation
```

**Response**:
```json
{
  "correlation": {
    "news_return_corr": 0.45,
    "corr_p_value": 0.021,
    "sentiment_return_corr": 0.32
  }
}
```

### Drawdown

```
GET /correlation/{symbol}/drawdown
```

**Response**:
```json
{
  "drawdown": {
    "drawdown_count": 2,
    "max_drawdown": -0.15,
    "drawdown_duration": 5
  }
}
```

## Next Steps

- [Pipeline Methods](pipeline-methods.md)
- [Rules DSL](rules-dsl.md)
- [Strategy Examples](examples.md)