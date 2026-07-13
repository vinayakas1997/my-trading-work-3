# Chaikin Money Flow (CMF)

## Why use it

- Measure buying vs selling pressure weighted by where close sits in the high–low range.
- Confirm whether rallies have institutional accumulation (positive CMF) or distribution (negative).
- Volume-quality filter for breakouts and trend continuations.

## What it is

- **Chaikin Money Flow** — 20-day sum of money flow volume / sum of volume.
- Range roughly −1 to +1; positive = accumulation bias, negative = distribution bias.
- **Inputs:** `high`, `low`, `close`, `volume` | **Outputs:** `cmf_20` | **Warmup:** 21 bars
- Period: **20** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `cmf_20` > 0 | Net buying pressure | Bullish bias; support long ideas |
| `cmf_20` < 0 | Net selling pressure | Bearish bias; caution on longs |
| `cmf_20` > +0.15 | Strong accumulation | Trend long confirmation |
| `cmf_20` < −0.15 | Strong distribution | Avoid longs; consider shorts |
| CMF rising while price flat | Hidden accumulation | Bullish setup brewing |
| CMF falling while price rises | Distribution | Bearish divergence |

## How to combine

- **OBV:** Both volume tools — agree direction for stronger signal (see `obv/README.md`).
- **Volume ratio:** High `volume_ratio_20` + positive CMF on breakout (see `volume_ratio/README.md`).
- **Trend:** Positive CMF + price > `sma_50` → qualified trend long (see `sma/README.md`).
- **Recipe:** `volume_pack`, `full_ta`.

## Caveats

- Thinly traded names give noisy CMF; minimum liquidity required.
- One-day block trades can skew the 20-day window.
- Not a standalone timing signal — use with price structure.

## Market notes

- **A — Generic daily equities:** Works on mid/high liquidity; avoid micro-caps with erratic volume.
- **B — India (NSE/BSE):** FII/DII flow days move CMF on index heavyweights; results season drives stock-specific CMF swings.
- **C — US equities:** End-of-quarter rebalancing can distort CMF on index constituents briefly.

## In this codebase

- Path: `indicators/chaikin_money_flow/chaikin_money_flow.py`
- Feature name: `cmf_20`
- Also included in: `volume_pack`, `full_ta`
