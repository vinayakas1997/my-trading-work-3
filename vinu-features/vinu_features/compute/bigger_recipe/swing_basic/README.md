# swing_basic

## Why use it

- Swing-trading preset balancing **trend (dual SMA)**, **timing (RSI)**, and **risk (volatility)**.
- Hold periods of roughly 1–4 weeks on daily bars — classic swing horizon.
- Avoid entries when `volatility_20d` is extreme without adjusting size.

## What it is

- **Swing trading preset** — four complementary features.
- **Recipe name:** `swing_basic` | **Warmup:** 100 bars | **Feature count:** 4
- **Outputs:** `sma_20`, `sma_100`, `rsi_14`, `volatility_20d`

## How to use it (workflow)

1. **Regime:** `sma_20` > `sma_100` → bullish swing regime; inverse for bearish.
2. **Pullback:** In bullish regime, wait for `rsi_14` < 40–50 (not necessarily oversold).
3. **Risk dial:** High `volatility_20d` → smaller position or wider stops.
4. **Entry:** Price reclaims `sma_20` after RSI cooldown in uptrend.

**Example signals (heuristic):**

| Setup | Action bias |
|---|---|
| Golden alignment + RSI dip + normal vol | Swing long candidate |
| `sma_20` < `sma_100` + RSI bounce | Counter-trend — lower conviction |
| Vol spike + trend break | Stand aside until vol settles |

## Components

| Feature | Guide |
|---|---|
| `sma_20`, `sma_100` | `indicators/sma/README.md` |
| `rsi_14` | `indicators/rsi/README.md` |
| `volatility_20d` | `indicators/volatility_20d/README.md` |

## Caveats

- No volume confirmation — add `volume_pack` for institutional flow.
- 100-bar warmup needed for `sma_100` — ensure sufficient history in request.
- Not a standalone system; define exits (ATR stops, time stops).

## Market notes

- **A — Generic daily equities:** Classic swing template on liquid mid/large caps.
- **B — India (NSE/BSE):** `sma_100` ~5 months of trading days; works on Nifty 100; illiquid names gap through SMAs.
- **C — US equities:** Earnings weeks inflate `volatility_20d` — pause new swings into binary events.

## In this codebase

- Path: `bigger_recipe/swing_basic/swing_basic.py`
- Request recipe: `swing_basic`
