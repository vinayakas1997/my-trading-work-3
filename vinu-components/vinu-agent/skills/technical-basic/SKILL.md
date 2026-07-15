---
name: technical-basic
description: Core technical analysis patterns, indicators, and charting methodology
category: technical
---

## Technical Analysis — Core Indicators

### Trend Indicators
| Indicator | Formula | Signal |
|-----------|---------|--------|
| SMA | mean(close, N) | Price above/below = trend direction |
| EMA | weighted mean(close, N) | Faster than SMA, less lag |
| MACD | EMA(12) - EMA(26); Signal = EMA(9) | Cross = trend change |
| ADX | DI+ and DI- smoothed | > 25 = trending, < 20 = ranging |

### Momentum Indicators
| Indicator | Signal Range | Interpretation |
|-----------|-------------|----------------|
| RSI | 0-100 | > 70 overbought, < 30 oversold |
| Stochastic | %K and %D lines | Cross above 20 = buy signal |
| CCI | -100 to +100 | > 100 overbought, < -100 oversold |
| ROC | percentage change N-periods | Acceleration/deceleration |

### Volume Indicators
- **OBV**: cumulative volume adjusted by price direction
- **Volume Profile**: volume at price levels (POC = Point of Control)
- **VWAP**: volume-weighted average price (institutional benchmark)
- **MFI**: money flow index (RSI with volume)

### Volatility Indicators
- **Bollinger Bands**: SMA ± 2σ → squeeze = breakout imminent
- **ATR**: average true range → stop loss placement (2-3x ATR)
- **Keltner Channels**: EMA ± ATR multiplier
- **KC + BB squeeze**: converging bands → breakout signal

### Candlestick Patterns
| Pattern | 2-candle | Signal |
|---------|----------|--------|
| Engulfing | Bearish/Bullish | Reversal |
| Harami | Small inside big | Trend pause |
| Doji | Single | Indecision |
| Hammer | Long lower wick | Bullish reversal |
| Shooting Star | Long upper wick | Bearish reversal |
