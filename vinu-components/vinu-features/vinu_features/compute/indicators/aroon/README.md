# Aroon

## Why use it

- Identify whether recent highs or lows are fresher — early trend emergence vs consolidation.
- Spot Aroon crossovers when one side dominates (new highs vs new lows).
- Complement ADX with a timing-oriented trend birth detector.

## What it is

- **Aroon indicator** — two lines measuring time since highest high and lowest low over N bars.
- Scale 0–100 for each line; higher `aroon_up` = recent highs; higher `aroon_down` = recent lows.
- **Inputs:** `high`, `low` | **Outputs:** `aroon_up`, `aroon_down` | **Warmup:** 26 bars
- Period: **25** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `aroon_up` > 70, `aroon_down` < 30 | Uptrend emerging | Bullish bias; buy pullbacks |
| `aroon_down` > 70, `aroon_up` < 30 | Downtrend emerging | Bearish bias; avoid longs |
| `aroon_up` crosses above `aroon_down` | Bullish crossover | Entry timing with trend filter |
| `aroon_down` crosses above `aroon_up` | Bearish crossover | Exit longs or short bias |
| Both < 50 | Consolidation | Range-trading environment |
| Both > 70 | Choppy high activity | No clear winner — stand aside |

## How to combine

- **ADX:** Aroon cross + `adx_14` rising above 20 → trend gaining strength (see `adx/README.md`).
- **SMA:** Bullish Aroon cross + price > `sma_20` → aligned swing long (see `sma/README.md`).
- **MACD:** Confirm direction with `macd` > 0 (see `macd/README.md`).
- **Recipe:** Included in `full_ta`.

## Caveats

- Sensitive to single spike highs/lows — one outlier bar can distort readings.
- Less popular than MACD/ADX — validate on your universe before relying on it.
- Not a standalone signal; crossovers need price confirmation.

## Market notes

- **A — Generic daily equities:** Works better on steady trenders than gap-heavy small caps.
- **B — India (NSE/BSE):** Circuit highs/lows reset Aroon abruptly; prefer names with continuous trading.
- **C — US equities:** Useful on sector ETFs with smooth trends; noisy on earnings-driven single names.

## In this codebase

- Path: `indicators/aroon/aroon.py`
- Feature names: `aroon_up`, `aroon_down`
- Also included in: `full_ta`
