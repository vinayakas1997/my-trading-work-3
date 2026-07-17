# mean_reversion_pack

## Why use it

- **Range-trading and fade toolkit** — RSI, Bollinger Bands, and Stochastic together.
- Identify stretched prices with multiple oscillator agreement.
- Best when ADX is low (no trend) — pair with `trend_pack` ADX check externally.

## What it is

- **RSI, Bollinger, stochastic mean-reversion bundle**
- **Recipe name:** `mean_reversion_pack` | **Warmup:** 21 bars | **Feature count:** 6
- **Outputs:** `rsi_14`, `bb_upper`, `bb_mid`, `bb_lower`, `stoch_k`, `stoch_d`

## How to use it (workflow)

1. **Range defined:** Price between `bb_lower` and `bb_upper` for several bars.
2. **Stretch:** Touch `bb_lower` + `rsi_14` < 30 + `stoch_k` < 20 → oversold cluster.
3. **Entry trigger:** `stoch_k` crosses above `stoch_d` at lower band.
4. **Target:** `bb_mid` or opposite band; **stop:** below recent low.

**Fade upper band:** Mirror logic at `bb_upper` with RSI > 70 and stoch > 80.

## Components

| Feature | Guide |
|---|---|
| `rsi_14` | `indicators/rsi/README.md` |
| `bb_upper`, `bb_mid`, `bb_lower` | `indicators/bollinger/README.md` |
| `stoch_k`, `stoch_d` | `indicators/stochastic/README.md` |

## Caveats

- **Dangerous in trends** — fading upper band in momentum names loses money.
- Require low ADX or explicit range structure before using this pack.
- Not a standalone system — define max loss per fade.

## Market notes

- **A — Generic daily equities:** Works on index ranges and sector consolidations.
- **B — India (NSE/BSE):** Circuit sequences break mean-reversion; avoid fading upper circuit stocks.
- **C — US equities:** SPX tight ranges suit this pack; growth momentum regimes do not.

## In this codebase

- Path: `bigger_recipe/mean_reversion_pack/mean_reversion_pack.py`
- Request recipe: `mean_reversion_pack`
