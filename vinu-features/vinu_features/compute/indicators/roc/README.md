# ROC (Rate of Change)

## Why use it

- Percentage momentum over 12 bars — comparable across stocks and sectors.
- Standard input for momentum factor ranks and relative-strength screens.
- Quick read: how much has price moved in % terms over ~2–3 trading weeks.

## What it is

- **Rate of Change** — `(close_t − close_{t−12}) / close_{t−12} × 100` (percent).
- +10 = up 10% vs 12 bars ago; −5 = down 5%.
- **Inputs:** `close` | **Outputs:** `roc_12` | **Warmup:** 13 bars
- Period: **12** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `roc_12` > 0 | Positive 12-bar momentum | Long bias in momentum strategies |
| `roc_12` < 0 | Negative momentum | Short/avoid in trend systems |
| `roc_12` > +15% | Strong winner | Leader list — watch extension risk |
| `roc_12` < −15% | Sharp loser | Oversold bounce vs falling knife |
| ROC improving (less negative) | Momentum repair | Early reversal watch |
| ROC deteriorating from high | Momentum fade | Take profits on leaders |

## How to combine

- **Momentum_10:** Absolute vs percent momentum (see `momentum_n/README.md`).
- **ADX:** High `roc_12` + `adx_14` > 25 → strong trending leader (see `adx/README.md`).
- **Mean reversion:** Extreme negative ROC + oversold `rsi_14` → bounce setup (see `rsi/README.md`).
- **Alpha158:** ROC family factors in qlib preset (see `bigger_recipe/alpha158/README.md`).

## Caveats

- Past winners can reverse — momentum crashes happen without warning.
- 12-day window is arbitrary; not optimal for all markets.
- Not a standalone signal; use in ranked universes or with risk controls.

## Market notes

- **A — Generic daily equities:** Core cross-sectional momentum factor; rank within sector for fairness.
- **B — India (NSE/BSE):** Strong ROC on small caps often liquidity-driven; verify volume with `volume_ratio_20`.
- **C — US equities:** Factor crowding in momentum ETFs can amplify ROC leaders/laggards at rebalances.

## In this codebase

- Path: `indicators/roc/roc.py`
- Feature name: `roc_12`
- Also included in: `full_ta`
