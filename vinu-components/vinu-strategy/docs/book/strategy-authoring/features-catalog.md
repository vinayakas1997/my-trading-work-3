# Feature Catalog

## Overview

This catalog lists all available features from **vinu-features** API that can be used in strategy configurations.

## Individual Indicators

### Moving Averages

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `sma_{period}` | Simple Moving Average | 1-500 | `sma_9`, `sma_20`, `sma_200` |
| `ema_{period}` | Exponential Moving Average | 1-500 | `ema_12`, `ema_26`, `ema_50` |

### Oscillators

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `rsi_{period}` | Relative Strength Index | 2-500 | `rsi_14`, `rsi_7`, `rsi_20` |
| `macd` | MACD line (EMA12-EMA26) | - | `macd` |
| `macd_signal` | MACD signal line (9-EMA of MACD) | - | `macd_signal` |
| `cci_{period}` | Commodity Channel Index | 2-500 | `cci_20` |
| `williams_r_{period}` | Williams %R | 2-500 | `williams_r_14` |

### Volatility Indicators

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `volatility_{period}d` | Rolling volatility | 2-500 | `volatility_20d`, `volatility_30d` |
| `atr_{period}` | Average True Range | 2-500 | `atr_14`, `atr_20` |

### Bollinger Bands

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `bb_upper_{period}` | Bollinger Upper Band | 2-500 | `bb_upper_20`, `bb_upper_30` |
| `bb_mid_{period}` | Bollinger Middle Band | 2-500 | `bb_mid_20`, `bb_mid_30` |
| `bb_lower_{period}` | Bollinger Lower Band | 2-500 | `bb_lower_20`, `bb_lower_30` |

### Stochastic

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `stoch_k_{period}` | Stochastic %K | 2-500 | `stoch_k_14` |
| `stoch_d_{period}` | Stochastic %D | 2-500 | `stoch_d_14` |

### Volume Indicators

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `obv` | On-Balance Volume | - | `obv` |
| `vwap` | Volume-Weighted Avg Price | - | `vwap` |
| `volume_ratio_{period}` | Volume vs MA volume | 2-500 | `volume_ratio_20` |
| `cmf_{period}` | Chaikin Money Flow | 2-500 | `cmf_20` |

### Price Action

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `daily_return` | Bar-over-bar close return | - | `daily_return` |
| `high_low_spread` | (high-low)/close | - | `high_low_spread` |
| `open_close_return` | Open-to-close return | - | `open_close_return` |
| `momentum_{period}` | Price momentum over N bars | 1-500 | `momentum_10`, `momentum_20` |
| `roc_{period}` | Rate of Change | 1-500 | `roc_12` |

### Trend Indicators

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `adx_{period}` | Avg Directional Index | 2-500 | `adx_14`, `adx_20` |
| `supertrend` | Supertrend (ATR-based) | - | `supertrend` |

### Aroon

| Feature | Description | Period | Example |
|---------|-------------|--------|---------|
| `aroon_up` | Aroon Up | 25 | `aroon_up` |
| `aroon_down` | Aroon Down | 25 | `aroon_down` |

## Preset Bundles

Instead of listing individual indicators, use these preset names:

| Preset | Features Included |
|--------|-------------------|
| `basic_ta` | sma_20, rsi_14, daily_return |
| `swing_basic` | sma_20, sma_100, rsi_14, volatility_20d |
| `momentum` | sma_10, sma_50, rsi_14, macd, macd_signal |
| `trend_pack` | sma_20, sma_50, ema_12, ema_26, macd, macd_signal, adx_14 |
| `volatility_pack` | atr_14, bb_upper, bb_mid, bb_lower, volatility_20d |
| `volume_pack` | obv, volume_ratio_20, cmf_20 |
| `mean_reversion_pack` | rsi_14, bb_upper, bb_mid, bb_lower, stoch_k, stoch_d |
| `full_ta` | All features from above presets combined |

## Usage Examples

### Individual Features

```yaml
features_required:
  - sma_9
  - sma_21
  - rsi_14
  - macd
  - macd_signal
```

### Preset Bundles

```yaml
features_required:
  - momentum
  - volatility_pack
```

### Mixed

```yaml
features_required:
  - basic_ta
  - volume_ratio_20
  - adx_14
```

## Case Sensitivity

Feature names are **case-insensitive** in evaluation:

```yaml
# All of these are equivalent:
features_required:
  - sma_20
  - SMA_20
  - Sma_20
```

## Feature Values

Each feature returns a numeric value:

| Feature Type | Example Value | Range |
|--------------|---------------|-------|
| Moving Averages | 175.50 | Price range |
| RSI | 45.2 | 0-100 |
| MACD | 0.123 | -inf to +inf |
| Volume Ratio | 1.5 | 0 to +inf |
| Momentum | 0.05 | -1 to +1 |
| CCI | 120.5 | -300 to +300 |

## Signal Field

All features include a `signal` field that aggregates the overall signal strength:

```json
{
  "symbol": "AAPL",
  "values": {
    "sma_9": 175.50,
    "sma_21": 172.30,
    "rsi_14": 45.2,
    "signal": 0.123
  }
}
```

**Signal calculation**: Aggregated from all requested features using a weighted combination.

## Best Practices

### 1. Request Only What You Need

```yaml
# Good - minimal features
features_required:
  - sma_9
  - sma_21

# Bad - requesting everything
features_required:
  - full_ta
```

### 2. Use Presets for Common Patterns

```yaml
# Good - use preset
features_required:
  - momentum

# Also good - explicit
features_required:
  - sma_10
  - sma_50
  - rsi_14
  - macd
  - macd_signal
```

### 3. Match Feature Names in Rules

```yaml
timing:
  rules:
    - name: ma_crossover
      when:
        - {source: features, key: sma_9, gt: sma_21}
```

## API Endpoint

```
GET /features/{symbol}?indicators=sma_9,sma_21,rsi_14
```

**Response**:
```json
{
  "symbol": "AAPL",
  "values": {
    "sma_9": 175.50,
    "sma_21": 172.30,
    "rsi_14": 45.2,
    "signal": 0.123
  }
}
```

## Next Steps

- [Correlation Fields](correlation-fields.md)
- [Pipeline Methods](pipeline-methods.md)
- [Rules DSL](rules-dsl.md)
- [Strategy Examples](examples.md)