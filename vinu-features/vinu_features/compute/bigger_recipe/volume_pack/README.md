# volume_pack

## Why use it

- **Participation quality** in one shot — OBV trend, relative volume, and Chaikin Money Flow.
- Confirm breakouts: price move + volume ratio + positive CMF.
- Detect distribution: price up but OBV/CMF weak.

## What it is

- **OBV, volume ratio, CMF bundle**
- **Recipe name:** `volume_pack` | **Warmup:** 21 bars | **Feature count:** 3
- **Outputs:** `obv`, `volume_ratio_20`, `cmf_20`

## How to use it (workflow)

1. **Conviction:** `volume_ratio_20` > 1.5 on move day → unusual participation.
2. **Direction of flow:** `cmf_20` > 0 → accumulation; < 0 → distribution.
3. **Trend of flow:** Rising OBV with rising price → healthy advance.
4. **Divergence:** Price up, OBV flat + CMF falling → fade or tighten stops.

**Breakout checklist:** High volume ratio + positive CMF + OBV breakout.

## Components

| Feature | Guide |
|---|---|
| `obv` | `indicators/obv/README.md` |
| `volume_ratio_20` | `indicators/volume_ratio/README.md` |
| `cmf_20` | `indicators/chaikin_money_flow/README.md` |

## Caveats

- Volume data quality critical — block deals distort CMF/OBV.
- No price levels — pair with `trend_pack` or `basic_ta`.
- Illiquid names give false volume signals.

## Market notes

- **A — Generic daily equities:** Most valuable on liquid mid/high cap universes.
- **B — India (NSE/BSE):** FII flow days move CMF on index weights; delivery % matters for conviction.
- **C — US equities:** OPEX/earnings volume spikes — compare ratio to symbol's own baseline.

## In this codebase

- Path: `bigger_recipe/volume_pack/volume_pack.py`
- Request recipe: `volume_pack`
