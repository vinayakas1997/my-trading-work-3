# Daily Return

## Why use it

- Base building block for risk, volatility, and ML label construction.
- Measure bar-over-bar percentage change — the raw material of momentum and mean-reversion research.
- Quick read on yesterday's move magnitude and direction for position review.

## What it is

- **Daily return** — `(close_t − close_{t−1}) / close_{t−1}`.
- Decimal form (0.02 = +2%); positive = up day, negative = down day.
- **Inputs:** `close` | **Outputs:** `daily_return` | **Warmup:** 2 bars

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| `daily_return` > 0 | Up day | Trend continuation context if series of green days |
| `daily_return` < 0 | Down day | Pullback in uptrend vs start of decline |
| |return| > 2–3% (large cap) | Event day — check news; widen vol expectations |
| |return| > 5% | Shock bar — revisit stops and `volatility_20d` |
| Cluster of small returns | Low vol grind | Compression — breakout watch |
| Series of same-sign returns | Momentum run | Ride trend; avoid fading without signal |

## How to combine

- **Volatility:** Feeds `volatility_20d` rolling std (see `volatility_20d/README.md`).
- **ML labels:** Basis for `forward_return_1` / `forward_return_5` targets (see `ml_models/labels/README.md`).
- **Momentum:** Complement `momentum_10` and `roc_12` for speed of move (see `momentum_n/README.md`, `roc/README.md`).
- **Recipe:** `basic_ta`, `full_ta`.

## Caveats

- Single-bar return is noisy — not a trading signal alone.
- Corporate actions (splits, dividends) should be adjusted in source data.
- Not a standalone entry rule.

## Market notes

- **A — Generic daily equities:** Universal input for quant features; discretionary traders use for post-move review.
- **B — India (NSE/BSE):** Circuit-filtered days cap daily return; gap between close and next open is not in this column (close-to-close only).
- **C — US equities:** Close-to-close misses overnight gap component; for gap-aware work use `open_close_return` too.

## In this codebase

- Path: `indicators/daily_return/daily_return.py`
- Feature name: `daily_return`
- Also included in: `basic_ta`, `full_ta`
