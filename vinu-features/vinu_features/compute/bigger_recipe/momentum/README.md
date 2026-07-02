# momentum

## Why use it

- Momentum and trend bundle — moving averages plus RSI and MACD in one preset.
- Answer: "Is this stock trending, and is momentum accelerating or fading?"
- Core discretionary stack for trend-following swing and position trades.

## What it is

- **Momentum and MACD bundle** — five aligned features.
- **Recipe name:** `momentum` | **Warmup:** 50 bars | **Feature count:** 5
- **Outputs:** `sma_10`, `sma_50`, `rsi_14`, `macd`, `macd_signal`

## How to use it (workflow)

1. **Trend:** `sma_10` > `sma_50` → short-term trend up.
2. **MACD:** `macd` > `macd_signal` and `macd` > 0 → momentum confirmed.
3. **RSI filter:** Avoid new longs if `rsi_14` > 75 unless breakout strategy.
4. **Exit:** MACD bearish cross or `sma_10` < `sma_50`.

**Scan order:** SMA alignment → MACD sign → MACD cross → RSI stretch check.

## Components

| Feature | Guide |
|---|---|
| `sma_10`, `sma_50` | `indicators/sma/README.md` |
| `rsi_14` | `indicators/rsi/README.md` |
| `macd`, `macd_signal` | `indicators/macd/README.md`, `indicators/macd_signal/README.md` |

## Caveats

- No ADX chop filter — add `trend_pack` for `adx_14` or check manually.
- MACD lags — late entries in fast markets.
- Not a standalone strategy; define risk per trade.

## Market notes

- **A — Generic daily equities:** Workhorse preset for trending sectors and indices.
- **B — India (NSE/BSE):** Popular combo on Bank Nifty / Nifty heavyweights; expiry volatility causes MACD whipsaws.
- **C — US equities:** Sector ETFs trend cleaner than single names; momentum preset shines on QQQ/XLK-style runs.

## In this codebase

- Path: `bigger_recipe/momentum/momentum.py`
- Request recipe: `momentum`
