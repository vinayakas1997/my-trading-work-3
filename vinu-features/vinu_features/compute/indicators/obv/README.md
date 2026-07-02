# OBV (On-Balance Volume)

## Why use it

- Track cumulative volume flow — whether volume accumulates on up days vs down days.
- Confirm price trends: rising price + rising OBV = healthy advance.
- Spot divergences: price new high but OBV flat/falling → weak participation.

## What it is

- **On-Balance Volume** — running sum adding volume on up closes, subtracting on down closes.
- Absolute level is arbitrary; **slope and divergence** matter, not the raw number.
- **Inputs:** `close`, `volume` | **Outputs:** `obv` | **Warmup:** 2 bars

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| OBV rising with price | Volume confirms uptrend | Hold or add longs |
| OBV falling with price | Volume confirms downtrend | Avoid longs |
| Price up, OBV flat/down | Bearish divergence | Tighten stops; distribution suspected |
| Price down, OBV flat/up | Bullish divergence | Watch for reversal / accumulation |
| OBV breakout with price | Participation surge | Higher conviction breakout |

## How to combine

- **CMF:** Money flow confirmation — `cmf_20` > 0 with rising OBV (see `chaikin_money_flow/README.md`).
- **Volume ratio:** Spike in `volume_ratio_20` on OBV breakout day (see `volume_ratio/README.md`).
- **MACD:** Price/MACD bull + OBV rising → aligned momentum (see `macd/README.md`).
- **Recipe:** `volume_pack`, `full_ta`.

## Caveats

- Level is cumulative from series start — only compare slope/divergence on same symbol.
- Volume data quality matters (splits, block prints, ADR volume).
- Not a standalone entry signal.

## Market notes

- **A — Generic daily equities:** Best on liquid names with reliable volume; weak on low-float stocks.
- **B — India (NSE/BSE):** Delivery volume vs intraday churn — OBV on NSE EQ series is standard; watch for bulk/block deal distortions.
- **C — US equities:** Dark pool activity not fully reflected; OBV still useful on ETFs and mega-caps.

## In this codebase

- Path: `indicators/obv/obv.py`
- Feature name: `obv`
- Also included in: `volume_pack`, `full_ta`
