# volatility_pack

## Why use it

- Unified **risk and envelope** view — ATR, Bollinger Bands, and return volatility.
- Size positions and stops from one preset instead of three separate requests.
- Spot squeezes (tight bands + low vol) and expansions (wide bands + high ATR).

## What it is

- **ATR, Bollinger, volatility bundle**
- **Recipe name:** `volatility_pack` | **Warmup:** 21 bars | **Feature count:** 5
- **Outputs:** `atr_14`, `bb_upper`, `bb_mid`, `bb_lower`, `volatility_20d`

## How to use it (workflow)

1. **Stop distance:** Use `atr_14` × 1.5–2.5 for swing stop placement.
2. **Stretch:** Price at `bb_upper` or `bb_lower` → mean-reversion or breakout context.
3. **Regime:** Rising `volatility_20d` → reduce size; falling → compression / breakout watch.
4. **Squeeze:** Narrow Bollinger width + low `volatility_20d` → prepare for expansion.

**Risk rule (heuristic):** Position size inversely related to `volatility_20d` percentile.

## Components

| Feature | Guide |
|---|---|
| `atr_14` | `indicators/atr/README.md` |
| `bb_upper`, `bb_mid`, `bb_lower` | `indicators/bollinger/README.md` |
| `volatility_20d` | `indicators/volatility_20d/README.md` |

## Caveats

- No directional bias — tells you *how much* not *which way*; pair with `trend_pack` or `momentum`.
- Band touches fail in strong trends (riding upper band).
- Not a standalone trading system.

## Market notes

- **A — Generic daily equities:** Essential risk preset before any discretionary entry.
- **B — India (NSE/BSE):** Budget/results spike all three vol measures — recalibrate after events.
- **C — US equities:** VIX spikes lead cash vol; use pack for single-name post-earnings sizing.

## In this codebase

- Path: `bigger_recipe/volatility_pack/volatility_pack.py`
- Request recipe: `volatility_pack`
