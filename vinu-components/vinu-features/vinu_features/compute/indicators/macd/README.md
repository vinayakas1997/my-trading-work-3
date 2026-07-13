# MACD

## Why use it

- Track momentum shift via the spread between fast and slow exponential moving averages.
- Identify bullish/bearish crossovers with the signal line and zero-line context.
- Spot divergences when price makes new extremes but MACD does not confirm.

## What it is

- **Moving Average Convergence Divergence** — MACD line = EMA(12) − EMA(26) of close.
- Positive MACD = short-term average above long-term (bullish momentum); negative = bearish.
- **Inputs:** `close` | **Outputs:** `macd` | **Warmup:** 34 bars
- Fast EMA: **12** | Slow EMA: **26** (signal line is separate: see `macd_signal/README.md`)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `macd` > 0 | Bullish momentum regime | Favor longs on pullbacks; avoid aggressive shorts |
| `macd` < 0 | Bearish momentum regime | Favor shorts on rallies; avoid aggressive longs |
| `macd` crosses above `macd_signal` | Bullish crossover | Entry timing when trend supports |
| `macd` crosses below `macd_signal` | Bearish crossover | Exit longs or initiate shorts |
| Histogram rising (macd − signal widening up) | Accelerating bullish momentum | Hold or trail stops |
| Bearish divergence | Price higher high, MACD lower high | Weakening uptrend — tighten risk |

## How to combine

- **Signal line:** Always read `macd` with `macd_signal` for crossovers (see `macd_signal/README.md`).
- **Trend:** `macd` > 0 and `adx_14` > 25 → confirmed trend (see `adx/README.md`).
- **EMA structure:** Price above `ema_26` + positive MACD → aligned uptrend (see `ema/README.md`).
- **Recipe:** Core of `momentum` and `trend_pack` presets.

## Caveats

- Lagging indicator — crossovers often fire late after a move has started.
- Whipsaws in sideways markets; filter with ADX or moving-average slope.
- Not a standalone signal; zero-line and crossover alone are insufficient without context.

## Market notes

- **A — Generic daily equities:** Standard 12/26/9 settings tuned for daily charts; less reliable on very low liquidity names.
- **B — India (NSE/BSE):** F&O expiry week volatility can produce false MACD crosses; combine with `atr_14` for stop sizing (see `atr/README.md`).
- **C — US equities:** Index products (SPY, QQQ) give cleaner MACD signals than single names with earnings gaps; watch macro event days (CPI, FOMC).

## In this codebase

- Path: `indicators/macd/macd.py`
- Feature name: `macd`
- Also included in: `momentum`, `trend_pack`, `full_ta`
