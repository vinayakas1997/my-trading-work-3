# Momentum (10-period)

## Why use it

- Raw price change over N bars — simplest trend-speed measure in absolute price units.
- Rank stocks by recent thrust for momentum screens and breakout lists.
- Complement percent-based `roc_12` when dollar move size matters for execution.

## What it is

- **10-period momentum** — `close_t − close_{t−10}` (absolute price difference, not percent).
- Positive = price higher than 10 bars ago; negative = lower.
- **Inputs:** `close` | **Outputs:** `momentum_10` | **Warmup:** 11 bars
- Period: **10** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `momentum_10` > 0 | Short-term upward thrust | Bullish momentum screen |
| `momentum_10` < 0 | Short-term downward thrust | Avoid longs in momentum systems |
| Rising momentum | Acceleration | Trend strength increasing |
| Falling momentum (still positive) | Deceleration | Late-stage trend — tighten risk |
| Cross from negative to positive | Momentum flip | Buy candidates in systematic strategies |
| Extreme vs history | Outlier move | Mean-revert risk or breakout continuation |

**Note:** Scale depends on stock price — ₹2000 stock vs ₹50 stock; use `roc_12` for comparable % moves.

## How to combine

- **ROC:** Percent version for cross-stock ranking (see `roc/README.md`).
- **SMA:** `momentum_10` > 0 and price > `sma_50` → aligned momentum trend (see `sma/README.md`).
- **RSI:** Momentum positive but RSI overbought → extended but strong (see `rsi/README.md`).
- **Recipe:** `full_ta`.

## Caveats

- Not normalized by price — compare within symbol or use ROC for universes.
- Lagging 10-day window — slow for very short-term scalping.
- Not a standalone signal.

## Market notes

- **A — Generic daily equities:** Classic Jegadeesh-Titman style momentum input on daily bars.
- **B — India (NSE/BSE):** Works on liquid Nifty 500; corporate actions must be adjusted in closes.
- **C — US equities:** Standard in cross-sectional momentum factors; pair with sector-neutral ranks for ML.

## In this codebase

- Path: `indicators/momentum_n/momentum_n.py`
- Feature name: `momentum_10`
- Also included in: `full_ta`
