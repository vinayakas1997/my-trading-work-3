# Stochastic Oscillator

## Why use it

- Show where the close sits within the recent high–low range (fast mean-reversion oscillator).
- Identify overbought/oversold extremes and %K / %D crossovers for timing entries.
- Complement RSI and Bollinger bands in range-bound or swing-trading setups.

## What it is

- **Stochastic oscillator** — %K measures close position in the N-bar range; %D is a smoothed %K.
- **Inputs:** `high`, `low`, `close` | **Outputs:** `stoch_k`, `stoch_d` | **Warmup:** 17 bars
- %K period: **14** | %D smooth: **3**

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `stoch_k` > 80 | Overbought — close near top of range | Avoid chasing; watch for %K crossing below %D |
| `stoch_k` < 20 | Oversold — close near bottom of range | Look for bounce when %K crosses above %D |
| %K crosses above %D | Bullish crossover | Entry timing in uptrend or at support |
| %K crosses below %D | Bearish crossover | Exit or short bias in downtrend |
| %K above %D in uptrend | Momentum aligned | Hold or add on pullbacks to 40–50 zone |

## How to combine

- **Bollinger:** `stoch_k` < 20 at `bb_lower` → classic mean-reversion long (see `bollinger/README.md`).
- **RSI:** Both `rsi_14` and `stoch_k` oversold → stronger exhaustion signal (see `rsi/README.md`).
- **Trend filter:** Only take bullish crossovers when `adx_14` > 20 and price above `sma_20` (see `adx/README.md`, `sma/README.md`).
- **Recipe:** Bundled in `mean_reversion_pack`.

## Caveats

- Whipsaws badly in strong trends — crossovers against the trend fail often.
- Not a standalone signal; range-bound markets suit stochastic best.
- Flat ranges (high = low) default %K to 50 in code — low volatility periods give muted readings.

## Market notes

- **A — Generic daily equities:** Best on 5–20 day swing horizons; less useful for multi-month trend following alone.
- **B — India (NSE/BSE):** Works well on liquid large-caps with normal daily ranges; avoid on penny stocks with single-tick ranges or frequent upper circuits.
- **C — US equities:** Earnings volatility expands ranges and can spike %K to extremes; reset expectations after gap events.

## In this codebase

- Path: `indicators/stochastic/stochastic.py`
- Feature names: `stoch_k`, `stoch_d`
- Also included in: `mean_reversion_pack`, `full_ta`
