# Volume Ratio (20-day)

## Why use it

- Compare today's volume to the recent average — spot unusual participation instantly.
- Confirm breakouts: valid moves often show volume > 1.5× average.
- Flag weak moves: price change on sub-normal volume lacks conviction.

## What it is

- **Volume ratio** — today's `volume` divided by 20-bar SMA of volume.
- 1.0 = average day; 2.0 = twice normal volume.
- **Inputs:** `volume` | **Outputs:** `volume_ratio_20` | **Warmup:** 21 bars
- Lookback: **20** bars

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `volume_ratio_20` ≈ 1.0 | Normal participation | No special volume signal |
| > 1.5 | Elevated volume | Breakout / news — check price direction |
| > 2.0 | Heavy volume | Institutional activity likely — high conviction bar |
| < 0.7 | Light volume | Weak move — fade or wait |
| High ratio + up close | Bullish conviction | Confirm long breakouts |
| High ratio + down close | Bearish conviction | Confirm breakdowns or distribution |

## How to combine

- **OBV / CMF:** Volume spike + positive money flow → strong long (see `obv/README.md`, `chaikin_money_flow/README.md`).
- **Bollinger:** Band break on volume > 1.5× → momentum continuation (see `bollinger/README.md`).
- **MACD:** Crossover on rising volume ratio → better MACD signal (see `macd/README.md`).
- **Recipe:** `volume_pack`, `full_ta`.

## Caveats

- Block/bulk deals and index rebalances create one-off spikes.
- Low liquidity names have erratic ratios — compare within symbol history.
- Not a standalone directional signal — always read with price action.

## Market notes

- **A — Generic daily equities:** 1.5× rule is a heuristic; adjust for symbol's typical volume pattern.
- **B — India (NSE/BSE):** Expiry week, budget, and results drive 3–5× volume on key names; index inclusion changes reset the baseline.
- **C — US equities:** Options expiry (OPEX), quad witching, and earnings create predictable volume surges.

## In this codebase

- Path: `indicators/volume_ratio/volume_ratio.py`
- Feature name: `volume_ratio_20`
- Also included in: `volume_pack`, `full_ta`
