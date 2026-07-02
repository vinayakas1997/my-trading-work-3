# trend_pack

## Why use it

- Full **trend confirmation stack** — SMA, EMA, MACD, and ADX together.
- Filter chop: only trade when ADX confirms directional energy.
- Institutional-style "is there a trend and is it tradeable?" answer in 7 columns.

## What it is

- **SMA/EMA/MACD/ADX trend bundle**
- **Recipe name:** `trend_pack` | **Warmup:** 50 bars | **Feature count:** 7
- **Outputs:** `sma_20`, `sma_50`, `ema_12`, `ema_26`, `macd`, `macd_signal`, `adx_14`

## How to use it (workflow)

1. **Structure:** Price > `sma_50` and `sma_20` > `sma_50` → uptrend structure.
2. **Speed:** `ema_12` > `ema_26` → faster trend confirmation.
3. **Momentum:** `macd` > `macd_signal` and `macd` > 0.
4. **Strength:** `adx_14` > 25 → trend strong enough to trade (not chop).

**Qualified long (heuristic):** All four checks pass → trend-following bias.

## Components

| Feature | Guide |
|---|---|
| `sma_20`, `sma_50` | `indicators/sma/README.md` |
| `ema_12`, `ema_26` | `indicators/ema/README.md` |
| `macd`, `macd_signal` | `indicators/macd/README.md`, `indicators/macd_signal/README.md` |
| `adx_14` | `indicators/adx/README.md` |

## Caveats

- No volume or volatility — pair with `volume_pack` or `volatility_pack`.
- Redundant signals (SMA + EMA + MACD) — by design for confirmation, not diversity.
- ADX lagging — may miss very early trend births.

## Market notes

- **A — Generic daily equities:** Best on names that trend for weeks (sector leaders).
- **B — India (NSE/BSE):** Nifty trend days show ADX + MACD alignment; range-bound midcaps fail ADX filter (good).
- **C — US equities:** Index and sector ETF trend systems; single-stock earnings can break all 7 signals at once.

## In this codebase

- Path: `bigger_recipe/trend_pack/trend_pack.py`
- Request recipe: `trend_pack`
