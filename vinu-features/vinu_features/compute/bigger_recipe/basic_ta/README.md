# basic_ta

## Why use it

- Fastest starter preset — trend, momentum, and return in one request (3 columns).
- Screen a universe without computing the full 31-column `full_ta` set.
- Good for dashboards, alerts, and teaching the engine workflow.

## What it is

- **Minimal trend and momentum bundle** — dispatches three standard indicators.
- **Recipe name:** `basic_ta` | **Warmup:** 21 bars | **Feature count:** 3
- **Outputs:** `sma_20`, `rsi_14`, `daily_return`

## How to use it (workflow)

1. **Trend:** Is price above or below `sma_20`? Above = short-term bullish structure.
2. **Momentum:** Is `rsi_14` stretched (>70 / <30) or neutral?
3. **Today's move:** `daily_return` shows bar-over-bar % change for context.

**Example decision tree (heuristic):**

| Condition | Interpretation |
|---|---|
| Price > `sma_20`, RSI 40–60 | Healthy uptrend — buy pullbacks |
| Price > `sma_20`, RSI > 70 | Extended — wait for cooldown |
| Price < `sma_20`, RSI < 30 | Downtrend + oversold — bounce only with confirmation |
| Large `daily_return` + RSI extreme | Event day — reduce size |

## Components

| Feature | Guide |
|---|---|
| `sma_20` | `indicators/sma/README.md` |
| `rsi_14` | `indicators/rsi/README.md` |
| `daily_return` | `indicators/daily_return/README.md` |

## Caveats

- Only 3 features — insufficient for volume or volatility context alone.
- Not a standalone strategy; add `volume_pack` or `volatility_pack` for fuller picture.
- Heuristics only — no guaranteed edge.

## Market notes

- **A — Generic daily equities:** Ideal first preset for single-symbol review.
- **B — India (NSE/BSE):** Quick scan of Nifty 50 names after close; watch gap days distorting `daily_return`.
- **C — US equities:** Good EOD checklist preset; pair with earnings calendar awareness.

## In this codebase

- Path: `bigger_recipe/basic_ta/basic_ta.py`
- Request recipe: `basic_ta` (expands via `catalog.resolve()`)
