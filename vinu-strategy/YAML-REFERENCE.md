# vinu-strategy YAML Authoring Guide

This document is the complete reference for writing strategy YAML files for vinu-strategy.
An AI agent can read this document to write valid strategies autonomously.

---

## 1. YAML Schema

```yaml
name:                  str (required)         — Unique strategy identifier
description:           str                    — Human-readable explanation
schedule:              "daily" | "weekly"     — Rebalance frequency
features_required:     list[str]              — Must pick from §2 (Feature Catalog)
correlation_required:  list[str]              — Must pick from §3 (Correlation Fields)
universe:
  source: "watchlist" | "inline"
  inline: [str]                               — Ticker list (required if source=inline)
pipeline:
  selection:           {method, params?}      — §4.1
  allocation:          {method, params?}      — §4.2
  timing:              {method, rules?}       — §4.3
  risk:                {method, params?}      — §4.4
```

---

## 2. Feature Catalog (vinu-features)

### 2.1 Individual Indicators (23 kinds)

These are parametric — specify the `kind` and `period` as the feature name.

| `features_required` name | Description | Param | Example |
|--------------------------|-------------|-------|---------|
| `sma_{period}` | Simple Moving Average | period: 1-500 | `sma_20`, `sma_9`, `sma_200` |
| `ema_{period}` | Exponential Moving Average | period: 1-500 | `ema_12`, `ema_26`, `ema_50` |
| `rsi_{period}` | Relative Strength Index | period: 2-500 | `rsi_14`, `rsi_7`, `rsi_20` |
| `macd` | MACD line (EMA12-EMA26) | — | `macd` |
| `macd_signal` | MACD signal line (9-EMA of MACD) | — | `macd_signal` |
| `daily_return` | Bar-over-bar close return | — | `daily_return` |
| `volatility_{period}d` | Rolling volatility | period: 2-500 | `volatility_20d`, `volatility_30d` |
| `atr_{period}` | Average True Range | period: 2-500 | `atr_14`, `atr_20` |
| `bb_upper_{period}` | Bollinger Upper Band | period: 2-500, std | `bb_upper_20`, `bb_upper_30` |
| `bb_mid_{period}` | Bollinger Middle Band | period: 2-500 | `bb_mid_20`, `bb_mid_30` |
| `bb_lower_{period}` | Bollinger Lower Band | period: 2-500 | `bb_lower_20`, `bb_lower_30` |
| `stoch_k_{period}` | Stochastic %K | period: 2-500 | `stoch_k_14` |
| `stoch_d_{period}` | Stochastic %D | period: 2-500 | `stoch_d_14` |
| `obv` | On-Balance Volume | — | `obv` |
| `vwap` | Volume-Weighted Avg Price | — | `vwap` |
| `volume_ratio_{period}` | Volume vs MA volume | period: 2-500 | `volume_ratio_20` |
| `high_low_spread` | (high-low)/close | — | `high_low_spread` |
| `open_close_return` | Open-to-close return | — | `open_close_return` |
| `momentum_{period}` | Price momentum over N bars | period: 1-500 | `momentum_10`, `momentum_20` |
| `roc_{period}` | Rate of Change | period: 1-500 | `roc_12` |
| `cci_{period}` | Commodity Channel Index | period: 2-500 | `cci_20` |
| `williams_r_{period}` | Williams %R | period: 2-500 | `williams_r_14` |
| `adx_{period}` | Avg Directional Index | period: 2-500 | `adx_14`, `adx_20` |
| `supertrend` | Supertrend (ATR-based) | — | `supertrend` |
| `cmf_{period}` | Chaikin Money Flow | period: 2-500 | `cmf_20` |
| `aroon_up` | Aroon Up | period: 25 | `aroon_up` |
| `aroon_down` | Aroon Down | period: 25 | `aroon_down` |

### 2.2 Legacy Aliases (also accepted)

- `bb_upper` = `bb_upper_20`, `bb_mid` = `bb_mid_20`, `bb_lower` = `bb_lower_20`
- `stoch_k` = `stoch_k_14`, `stoch_d` = `stoch_d_14`
- `volatility_20d` (period=20)
- `macd`, `macd_signal`, `aroon_up`, `aroon_down`

### 2.3 Preset Bundles

Instead of listing individual indicators, you can list these preset names in `features_required`:

| Preset | Features included |
|--------|-------------------|
| `basic_ta` | sma_20, rsi_14, daily_return |
| `swing_basic` | sma_20, sma_100, rsi_14, volatility_20d |
| `momentum` | sma_10, sma_50, rsi_14, macd, macd_signal |
| `trend_pack` | sma_20, sma_50, ema_12, ema_26, macd, macd_signal, adx_14 |
| `volatility_pack` | atr_14, bb_upper, bb_mid, bb_lower, volatility_20d |
| `volume_pack` | obv, volume_ratio_20, cmf_20 |
| `mean_reversion_pack` | rsi_14, bb_upper, bb_mid, bb_lower, stoch_k, stoch_d |
| `full_ta` | All 33 columns from above presets combined |

---

## 3. Correlation Fields (vinu-correlation)

List in `correlation_required` to make these fields available in rule conditions
under `source: correlation`.

| Field name | Type | Description | Example value |
|------------|------|-------------|---------------|
| `impact` | object | Fetch impact data for conditions | — |
| `granger` | object | Fetch Granger causality data | — |
| `correlation` | object | Fetch Pearson correlation data | — |
| `drawdown` | object | Fetch drawdown attribution data | — |

When listed, these keys become available in rule conditions as `correlation.<key>`:

| Condition key (`source: correlation, key: ...`) | Type | Description |
|--------------------------------------------------|------|-------------|
| `high_impact_bullish_events` | int | # of bullish news with high price impact |
| `high_impact_bearish_events` | int | # of bearish news with high price impact |
| `avg_price_drop_30m` | float | Avg 30m price drop for bearish events |
| `event_count` | int | Total impact events |
| `news_return_corr` | float | Pearson correlation (news volume vs returns) |
| `corr_p_value` | float | P-value of correlation |
| `sentiment_return_corr` | float | Correlation (sentiment vs returns) |
| `granger_p_value` | float | Granger causality p-value |
| `granger_causes_prices` | bool | Whether news Granger-causes price at 95% CI |
| `best_lag_minutes` | int | Best predictive lag in minutes |
| `best_lag_correlation` | float | Correlation at best lag |
| `drawdown_count` | int | Number of significant drawdowns detected |

---

## 4. Pipeline Method Catalog

### 4.1 Selection — `pipeline.selection`

| Method | Params | Behavior |
|--------|--------|----------|
| `all` | — | Passes entire universe through. No filtering. |
| `threshold` | `on` (str): signal field name, `min` (float): minimum value | Keeps symbols where signal >= min |
| `top_n` | `n` (int): max symbols to keep | Keeps top N symbols by signal value |

### 4.2 Allocation — `pipeline.allocation`

| Method | Params | Behavior |
|--------|--------|----------|
| `equal` | — | Equal weight 1/N for all candidates |
| `signal_scaled` | `signal` (str): optional signal expression | Weight proportional to signal value |

### 4.3 Timing — `pipeline.timing`

| Method | Params | Behavior |
|--------|--------|----------|
| `none` | — | No timing adjustments. Pass-through. |
| `rules` | `rules` (list of Rule objects) | Evaluate rules per symbol (see §5) |

### 4.4 Risk — `pipeline.risk`

| Method | Params | Behavior |
|--------|--------|----------|
| `normalize` | `max_weight` (float, default 0.25), `cash_floor` (float, default 0.10) | Cap individual weights, reserve cash floor |
| `none` | — | Pass-through without modification |

---

## 5. Rules DSL Reference

### 5.1 Rule Structure

```yaml
rules:
  - name: unique_rule_name
    when:
      - {source: "features" | "correlation", key: "<field_name>", <operator>: <value>}
      - {source: "features" | "correlation", key: "<field_name>", <operator>: <value>}
    then: {action: "<action_type>", value: <float>}
```

### 5.2 Valid Sources

| Source | Key examples |
|--------|-------------|
| `features` | Any indicator from §2, e.g. `RSI_14`, `ADX_14`, `sma_9`, `MOM_20` |
| `correlation` | Any field from §3, e.g. `high_impact_bullish_events`, `granger_causes_prices`, `drawdown_count` |

### 5.3 Valid Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `eq` | equals | `key: "granger_causes_prices", eq: true` |
| `neq` | not equals | `key: "status", neq: "closed"` |
| `gt` | greater than | `key: "RSI_14", gt: 70` |
| `gte` | greater or equal | `key: "MOM_20", gte: 0.0` |
| `lt` | less than | `key: "RSI_14", lt: 30` |
| `lte` | less or equal | `key: "weight", lte: 0.25` |
| `in` | in list | `key: "sector", in: ["Tech", "Healthcare"]` |
| `between` | between (inclusive) | `key: "adx_14", between: [20, 40]` |

### 5.4 Valid Actions

| Action | Effect | Use case |
|--------|--------|----------|
| `weight_add` | `current += value` | Boost weight on bullish signal |
| `weight_subtract` | `current -= value` | Reduce weight on caution signal |
| `weight_multiply` | `current *= value` | Scale weight (e.g. 1.20 = +20%) |
| `weight_set` | `current = value` | Force specific weight (e.g. 0.0 to go to cash) |

### 5.5 Rule Evaluation

- All conditions in `when` are AND-ed — every condition must be true for the rule to fire.
- Rules are evaluated **sequentially** per symbol, so later rules can override earlier ones.
- Use `--trace` flag in CLI to see which rules fired and why.

---

## 6. Complete Examples

### Simple MA Crossover

```yaml
name: ma_crossover
description: "9/21 SMA crossover"
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
```

### News-Aware Momentum with Drawdown Protection

```yaml
name: news_aware_momentum
description: "Momentum with correlation rules"
schedule: daily
features_required:
  - momentum_20
  - adx_14
correlation_required:
  - impact
  - granger
  - drawdown
pipeline:
  selection:
    method: threshold
    on: momentum_20
    min: 0.0
  allocation:
    method: signal_scaled
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
```

### Custom: RSI Mean Reversion with Volume Confirmation

```yaml
name: rsi_volume_reversion
description: "RSI oversold with high volume confirmation"
schedule: daily
features_required:
  - rsi_14
  - volume_ratio_20
pipeline:
  selection:
    method: all
  allocation:
    method: equal
  timing:
    method: rules
    rules:
      - name: oversold_with_volume
        when:
          - {source: features, key: rsi_14, lt: 30}
          - {source: features, key: volume_ratio_20, gt: 1.5}
        then: {action: weight_add, value: 0.10}
      - name: overbought_caution
        when:
          - {source: features, key: rsi_14, gt: 70}
        then: {action: weight_set, value: 0.0}
  risk:
    method: normalize
    max_weight: 0.25
    cash_floor: 0.20
```

---

## 7. Validation Tips

- Run `vinu-strategy reload` after adding/changing YAML files to reload the registry
- Run `vinu-strategy evaluate <name> --ticker AAPL --trace` to test with rule trace
- Check the `rule_trace` section in the output to verify conditions are evaluating correctly
- Each feature name must match exactly from §2 (case-insensitive matching is supported)
