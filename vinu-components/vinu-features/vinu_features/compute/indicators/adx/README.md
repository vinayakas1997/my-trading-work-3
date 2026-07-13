# ADX (Average Directional Index)

## Why use it

- Measure **trend strength**, not direction — filter out choppy, low-edge markets.
- Decide when to run trend-following vs mean-reversion strategies.
- Confirm that a breakout or moving-average signal has directional energy behind it.

## What it is

- **Average Directional Index** — smoothed magnitude of directional movement (from +DI and −DI).
- Scale 0–100; higher = stronger trend (regardless of up or down).
- **Inputs:** `high`, `low`, `close` | **Outputs:** `adx_14` | **Warmup:** 28 bars
- Period: **14** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `adx_14` < 20 | Weak / absent trend | Avoid trend breakouts; favor range tools (RSI, Bollinger) |
| 20–25 | Trend emerging | Watch for price structure confirmation |
| 25–50 | Strong trend | Trend-following systems in play |
| > 50 | Very strong trend | Ride trend; avoid fading without clear reversal |
| Rising ADX | Trend strengthening | Add to winners or trail stops |
| Falling ADX | Trend weakening | Take profits; prepare for range |

**Direction:** Pair with price vs `sma_50` or `macd` sign for bullish vs bearish trend.

## How to combine

- **Trend filter:** Only take MACD crosses when `adx_14` > 20 (see `macd/README.md`).
- **SMA:** Price above `sma_50` + ADX > 25 → qualified uptrend (see `sma/README.md`).
- **ATR:** Size stops with `atr_14` when ADX confirms trend (see `atr/README.md`).
- **Recipe:** Included in `trend_pack`, `full_ta`.

## Caveats

- ADX does not tell direction — always pair with price or MACD.
- Can stay elevated late in a trend (exhaustion risk).
- Not a standalone entry signal; it is a regime filter.

## Market notes

- **A — Generic daily equities:** ADX 25 rule is a heuristic; sector ETFs often trend cleaner than single names.
- **B — India (NSE/BSE):** Strong ADX common in trending large caps (Reliance, HDFC Bank cycles); index-wide ADX useful for Nifty trend days.
- **C — US equities:** Index ADX (SPY) for macro regime; single-name ADX spikes around M&A or sector re-ratings.

## In this codebase

- Path: `indicators/adx/adx.py`
- Feature name: `adx_14`
- Also included in: `trend_pack`, `full_ta`
