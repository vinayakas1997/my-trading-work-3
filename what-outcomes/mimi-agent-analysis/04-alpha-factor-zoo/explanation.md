# Angle 04: Alpha Factor Zoo — Explanation

## Objective
Catalog and compute the 461+ pre-built alpha factors available in the features service across five factor families, testing compute performance, theme coverage, and API accessibility.

## Factor Registry Summary

| Family | Count | Source | Theme Focus |
|--------|-------|--------|-------------|
| alpha101 | 101 | WorldQuant 101 alphas | Momentum, reversal, volume, volatility |
| gtja191 | 191 | Guotai Junan 191 factors | Volume, momentum, reversal, volatility |
| qlib158 | 154 | Microsoft Qlib 158 factors | Momentum, volume, microstructure |
| academic | 11 | Academic literature (BAB, HML, etc.) | Value, volatility, momentum |
| fundamental | 4 | Fundamental ratios (ROE, asset growth, etc.) | Quality, growth, value |
| **Total** | **461** | | |

### Theme Distribution
- **Volume** (167): Largest theme — turnover, dollar volume, volume ratios
- **Momentum** (159): Price momentum, moving averages, ROC, MACD variants
- **Reversal** (78): Short-term mean reversion, contrarian signals
- **Volatility** (28): Standard deviation, ATR, beta variants
- **Microstructure** (17): Bid-ask spread proxies, tick-level patterns
- **Quality** (5): Profitability ratios
- **Liquidity** (3): Turnover-based liquidity measures
- **Value** (2): Book-to-market, earnings yield
- **Growth** (1): Earnings growth
- **Sentiment** (1): Price-based sentiment proxy

### Universe Distribution
- **equity_us** (270): alpha101, qlib158, academic, fundamental
- **equity_cn** (191): gtja191 (China A-share universe)

### Decay Horizon Distribution
- **1 bar** (21): Ultra-fast signals
- **5 bars** (149): Short-term (most common)
- **10 bars** (39): Medium-short
- **20 bars** (73): Medium
- **60 bars** (47): Medium-long
- **252 bars** (5): Annual horizon (academic factors)
- **Other** (127): Custom/variable horizons

## Compute Paths

### Path 1: HTTP API Presets (11 available)
| Preset | Features | Works? | Notes |
|--------|----------|--------|-------|
| `alpha101` | 101 | ✅ | 4T×1d=504 rows in 3.8s; 4T×15m=29875 rows in 3.9s |
| `alpha158` | 158 | ✅ | |
| `alpha360` | 360 | ✅ | |
| `basic_ta` | 3 | ✅ | sma_20, rsi_14, daily_return |
| `full_ta` | 32 | ✅ | SMA/EMA/RSI/MACD/Bollinger/Stoch/ATR/ADX/OBV |
| `mean_reversion_pack` | 6 | ✅ | RSI, Bollinger %b/width, stochastic |
| `momentum` | 5 | ✅ | ROC, momentum, MACD line/signal/hist |
| `swing_basic` | 4 | ✅ | Swing entry/exit signals |
| `trend_pack` | 7 | ✅ | SMA/EMA/MACD/ADX |
| `volatility_pack` | 5 | ✅ | ATR, Bollinger bands, volatility |
| `volume_pack` | 3 | ✅ | OBV, volume ratio, CMF |

### Path 2: Python Module Import (all 461 factors)
```python
from vinu_features.compute.alpha_factors.gtja191.alpha_001 import compute
result = compute(panel)  # panel = dict[str, pd.DataFrame]
```

### Path 3: Expression DSL
```python
from vinu_features.compute.factor_expressions import compute_expression
result = compute_expression("rank(gtja191_001) * zscore(alpha101_005)", panel)
```

## Compute Performance

| Preset | Tickers | Interval | Bars | Factors | Time |
|--------|---------|----------|------|---------|------|
| alpha101 | 4 | 1d | 504 | 101 | 3.8s |
| alpha101 | 1 | 1h | 1883 | 101 | 2.5s |
| alpha101 | 4 | 1h | 7532 | 101 | 3.6s |
| alpha101 | 1 | 15m | 7487 | 101 | 2.6s |
| alpha101 | 4 | 15m | 29875 | 101 | 3.9s |
| alpha158 | 1 | 1d | 126 | 158 | 2.6s |
| alpha360 | 1 | 1d | 126 | 360 | 2.5s |
| TA presets | 1 | 1d | 126 | 3-32 | 2.5s each |

## Three Compute Paths Summary

1. **HTTP API** (`/requests` + `preset` param) — quickest, 11 presets, works for alpha101/alpha158/alpha360 + TA packs
2. **Python module import** (`alpha_factors/*/alpha_*.py`) — all 461 factors, requires local Python process
3. **Expression DSL** (`factor_expressions.compute_expression`) — combines multiple factors via string expressions
