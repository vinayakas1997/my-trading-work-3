# MACD Signal

## Why use it

- Smooth the raw MACD line to generate actionable crossover signals.
- Reduce noise vs reading MACD alone; standard 9-period EMA of MACD is the industry default.
- Define the MACD histogram implicitly: `macd` − `macd_signal`.

## What it is

- **MACD signal line** — 9-period EMA of the MACD line (EMA12 − EMA26).
- Crossovers between `macd` and `macd_signal` are the primary MACD trading triggers.
- **Inputs:** `close` | **Outputs:** `macd_signal` | **Warmup:** 34 bars
- Signal EMA period: **9** | Underlying MACD: EMA **12** / **26**

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `macd` > `macd_signal` | Bullish configuration | Bias long; signal line acts as dynamic support for MACD |
| `macd` < `macd_signal` | Bearish configuration | Bias short or flat |
| `macd` crosses above `macd_signal` | Bullish crossover | Buy trigger when trend filter agrees |
| `macd` crosses below `macd_signal` | Bearish crossover | Sell / cover trigger |
| `macd` and signal both below 0, then bullish cross | Bear-market rally or reversal start | Wait for price confirmation above `sma_20` |
| Both above 0, bearish cross | Uptrend pause or reversal | Trail stops; do not ignore in mature trends |

## How to combine

- **MACD line:** Always use together with `macd` (see `macd/README.md`).
- **RSI:** Bullish MACD cross + `rsi_14` exiting oversold → stronger reversal (see `rsi/README.md`).
- **Volume:** Crossover on rising `volume_ratio_20` → higher conviction (see `volume_ratio/README.md`).
- **Recipe:** Bundled in `momentum` and `trend_pack`.

## Caveats

- Crossovers lag price; late entries are common in fast markets.
- Multiple crosses in chop = whipsaw — require ADX or range definition.
- Not a standalone signal; always pair with trend and risk management.

## Market notes

- **A — Generic daily equities:** Signal line cross is a timing tool, not a strategy — position sizing and stops matter more.
- **B — India (NSE/BSE):** On mid/small caps, slippage on crossover day can erase edge; prefer liquid names for MACD systems.
- **C — US equities:** After-hours news can gap through your crossover level; daily close-based MACD updates only once per session.

## In this codebase

- Path: `indicators/macd_signal/macd_signal.py`
- Feature name: `macd_signal`
- Also included in: `momentum`, `trend_pack`, `full_ta`
