# Williams %R

## Why use it

- Fast oscillator showing where close sits in the N-bar high–low range (inverse of stochastic logic).
- Flag overbought/oversold extremes for short-term swing entries and exits.
- Pair with trend filters when fading extremes or buying pullbacks.

## What it is

- **Williams %R** — measures distance from the highest high over 14 bars; scale **−100 to 0**.
- Closer to 0 = closer to recent highs (overbought); closer to −100 = near recent lows (oversold).
- **Inputs:** `high`, `low`, `close` | **Outputs:** `williams_r_14` | **Warmup:** 15 bars
- Period: **14** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| > −20 | Overbought — price near top of 14-bar range | Caution on new longs; watch for roll from −20 |
| > −10 | Extreme overbought | Reversal risk in ranges |
| < −80 | Oversold — price near bottom of range | Look for bounce toward −50 |
| < −90 | Extreme oversold | Capitulation / sharp snapback setups |
| −50 zone | Mid-range | No clear edge alone |

**Note:** %R is inverted vs RSI — high readings (near 0) = overbought.

## How to combine

- **Stochastic:** `williams_r_14` < −80 and `stoch_k` < 20 → double oversold (see `stochastic/README.md`).
- **RSI:** Confirm exhaustion when both oscillators agree (see `rsi/README.md`).
- **Trend:** Buy oversold only when price holds above `ema_50` or `sma_50` (see `ema/README.md`, `sma/README.md`).
- **Supertrend:** Oversold + price above `supertrend` → pullback in uptrend (see `supertrend/README.md`).

## Caveats

- Very sensitive — many false signals without a trend filter.
- Not a standalone signal; strong trends stay overbought/oversold.
- Same range-compression issue as stochastic when high ≈ low.

## Market notes

- **A — Generic daily equities:** Best as a timing tool on 1–2 week swings, not long-term investing.
- **B — India (NSE/BSE):** Upper/lower circuit days pin %R at extremes; wait for tradeable range to resume.
- **C — US equities:** Pre-market gap moves can push %R to −5 or −95 on the open print; use close-based confirmation.

## In this codebase

- Path: `indicators/williams_r/williams_r.py`
- Feature name: `williams_r_14`
- Also included in: `full_ta`
