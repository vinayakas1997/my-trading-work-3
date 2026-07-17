# CCI (Commodity Channel Index)

## Why use it

- Measure how far typical price deviates from its recent average (cyclical turning points).
- Spot overbought/oversold extremes and zero-line crosses for momentum shifts.
- Useful when price is choppy but still mean-reverting around a central value.

## What it is

- **Commodity Channel Index** — deviation of typical price `(H+L+C)/3` from its 20-bar mean, scaled by mean absolute deviation.
- Unbounded scale; commonly read with ±100 and ±200 bands.
- **Inputs:** `high`, `low`, `close` | **Outputs:** `cci_20` | **Warmup:** 21 bars
- Period: **20** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| > +100 | Above normal range — bullish strength | Trend continuation or late-stage chase risk |
| > +200 | Extreme overbought | Fade only with confirmation; trends can ride +200 |
| < −100 | Below normal range — bearish pressure | Avoid longs; look for stabilization |
| < −200 | Extreme oversold | Bounce setups in range markets |
| Cross above 0 | Shift to bullish momentum | Buy pullbacks in emerging uptrends |
| Cross below 0 | Shift to bearish momentum | Sell rallies in downtrends |

## How to combine

- **Trend:** `cci_20` > 0 and `adx_14` > 25 → trend with momentum (see `adx/README.md`).
- **Bollinger:** CCI < −100 at `bb_lower` → stretched mean-reversion (see `bollinger/README.md`).
- **Volume:** CCI spike + rising `cmf_20` → move supported by money flow (see `chaikin_money_flow/README.md`).
- **Williams %R:** Both deeply oversold → stronger reversal confluence (see `williams_r/README.md`).

## Caveats

- No fixed ceiling/floor — "extreme" levels vary by volatility regime.
- Not a standalone signal; zero-line crosses whipsaw in sideways markets.
- Lagging vs raw price; combine with structure and volume.

## Market notes

- **A — Generic daily equities:** ±100 bands are heuristics; adjust expectations in high-volatility sectors (commodities, small caps).
- **B — India (NSE/BSE):** Circuit limits and gap opens can spike CCI instantly; more reliable on Nifty constituents than illiquid small caps.
- **C — US equities:** Sector rotation days can push CCI extremes across a group simultaneously — cross-sectional context matters for relative value.

## In this codebase

- Path: `indicators/cci/cci.py`
- Feature name: `cci_20`
- Also included in: `full_ta`
