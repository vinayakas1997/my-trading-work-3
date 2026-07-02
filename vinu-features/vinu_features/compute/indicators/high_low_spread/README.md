# High-Low Spread

## Why use it

- Normalize the day's trading range as a fraction of price — intraday volatility at a glance.
- Spot wide-range days (emotion, news) vs narrow inside days (compression).
- Context for stop placement: wide spread day = wider noise band.

## What it is

- **High-low spread** — `(high − low) / close` per bar.
- Higher = wider range relative to closing price (more intraday volatility).
- **Inputs:** `high`, `low`, `close` | **Outputs:** `high_low_spread` | **Warmup:** 1 bar

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Low spread (< 1% large caps) | Quiet / inside day | Compression — breakout may follow |
| High spread (> 3–4%) | Wide battleground | Event or trend acceleration — widen stops |
| Rising spread series | Volatility expanding | Reduce size; trend or chaos |
| Narrow spread after trend | Flag / pause | Continuation or reversal pending |
| Wide spread + small body (OC small) | Indecision / rejection | Watch next day direction |

## How to combine

- **ATR:** Related vol measure — ATR in absolute terms, spread as % of price (see `atr/README.md`).
- **Open-close return:** Wide spread + bullish OC → strong close near highs (see `open_close_return/README.md`).
- **Bollinger squeeze:** Narrow spreads often precede band expansion (see `bollinger/README.md`).
- **Recipe:** `full_ta`.

## Caveats

- Single-bar measure — one outlier wick inflates spread.
- Compare within symbol history; cross-stock levels differ by liquidity and price.
- Not a directional signal alone.

## Market notes

- **A — Generic daily equities:** Useful filter for "tradeable range" vs dead names.
- **B — India (NSE/BSE):** Circuit days compress or cap spread artificially; true range may be truncated.
- **C — US equities:** Biotech FDA days can show 20%+ spreads; adjust expectations by sector.

## In this codebase

- Path: `indicators/high_low_spread/high_low_spread.py`
- Feature name: `high_low_spread`
- Also included in: `full_ta`
