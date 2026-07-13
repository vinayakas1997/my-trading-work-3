# RSI

## Why use it

- Measure whether recent buying or selling pressure is stretched (momentum vs mean-reversion context).
- Filter entries: avoid chasing when buyers are already saturated; spot exhaustion for reversals or pullbacks.
- Spot divergences between price and momentum (price new high, RSI lower high).

## What it is

- **Relative Strength Index** — compares average gains vs average losses over a lookback window.
- Range 0–100; higher = more recent upward pressure.
- **Inputs:** `close` | **Outputs:** `rsi_14` | **Warmup:** 15 bars
- Period: **14** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| > 70 | Overbought — buyers may be saturated | Caution on new longs; watch for fade or consolidation |
| > 80 | Extreme overbought | High reversal risk in range-bound markets |
| < 30 | Oversold — sellers exhausted | Look for bounce or stabilization |
| < 20 | Extreme oversold | Capitulation / sharp bounce setups (with confirmation) |
| 40–60 | Neutral | No edge alone; combine with trend and volume |

**Divergence:** Price makes a higher high but RSI makes a lower high → bearish momentum divergence (and vice versa for bullish).

## How to combine

- **Trend filter:** `rsi_14` < 30 and price above `sma_50` → pullback buy in an uptrend (see `sma/README.md`).
- **MACD confirmation:** RSI oversold + `macd` crossing above `macd_signal` → momentum turning up (see `macd/README.md`).
- **Volume:** RSI high + falling `volume_ratio_20` → weak breakout (see `volume_ratio/README.md`).
- **Mean-reversion pack:** Use inside `mean_reversion_pack` with Bollinger and stochastic.

## Caveats

- Strong trends can keep RSI overbought or oversold for long stretches — do not fade blindly.
- Not a standalone entry signal; always add trend structure, support/resistance, or volume context.
- Single-bar gaps can distort the 14-day average; check raw price action after large gaps.

## Market notes

- **A — Generic daily equities:** Classic 30/70 thresholds work best in ranging markets; in trends, use RSI for pullbacks only (buy dips when RSI cools in uptrend).
- **B — India (NSE/BSE):** Gap-up opens (limit-up moves, strong FII flows) can pin RSI near 100 for days; circuit-hit stocks show distorted readings. Prefer RSI on liquid Nifty 50 / large-cap names.
- **C — US equities:** Earnings gaps and pre-market gaps feed into the 14-day window; post-earnings drift can leave RSI elevated while fundamentals have changed. Less meaningful on low-float meme names with violent squeezes.

## In this codebase

- Path: `indicators/rsi/rsi.py`
- Feature name: `rsi_14`
- Also included in recipes: `basic_ta`, `swing_basic`, `momentum`, `mean_reversion_pack`, `full_ta`
