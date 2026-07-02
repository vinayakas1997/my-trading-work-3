# Supertrend

## Why use it

- ATR-based trailing stop line that flips trend direction when price breaks the band.
- Simple visual rule: stay long when price is above supertrend, exit/short when below.
- Position sizing companion — distance to supertrend scales with volatility.

## What it is

- **Supertrend** — trailing level derived from median price ± 3× ATR(14).
- Output is the active support (uptrend) or resistance (downtrend) line value.
- **Inputs:** `high`, `low`, `close` | **Outputs:** `supertrend` | **Warmup:** 15 bars
- ATR period: **14** | Multiplier: **3.0** (fixed in code; uses `atr_14` internally)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Close > `supertrend` | Bullish regime | Hold longs; supertrend line as trailing stop |
| Close < `supertrend` | Bearish regime | Flat or short bias |
| Flip: close crosses above `supertrend` | Bullish flip | Buy signal in trend-following systems |
| Flip: close crosses below `supertrend` | Bearish flip | Sell / cover signal |
| Price hugging supertrend | Strong trend | Trail stop; avoid wide mean-reversion bets |

## How to combine

- **ATR:** Same volatility engine — widen mental stops when `atr_14` expands (see `atr/README.md`).
- **ADX:** Take flips only when `adx_14` > 20 to skip chop (see `adx/README.md`).
- **RSI:** Bullish flip + `rsi_14` not overbought → better risk/reward entry (see `rsi/README.md`).
- **Volume:** Flip on high `volume_ratio_20` → stronger conviction (see `volume_ratio/README.md`).

## Caveats

- Whipsaws in sideways markets — multiple flips erode capital.
- Multiplier 3 is fixed; tight in low vol, loose in high vol — not adaptive to regime.
- Not a standalone signal; combine with regime filter and position sizing.

## Market notes

- **A — Generic daily equities:** Popular on daily swing systems; less common for long-only buy-and-hold.
- **B — India (NSE/BSE):** Used by many retail trend systems on Nifty/Bank Nifty daily charts; gap opens can trigger false flips.
- **C — US equities:** Works on liquid ETFs; single stocks with overnight gaps need wider discretion than the line alone.

## In this codebase

- Path: `indicators/supertrend/supertrend.py`
- Feature name: `supertrend`
- Also included in: `full_ta`
