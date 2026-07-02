# EMA (Exponential Moving Average)

## Why use it

- Track trend with more weight on recent prices than SMA (faster response).
- Build MACD (EMA12 − EMA26) and other momentum systems.
- Use as dynamic support/resistance for active swing and position trading.

## What it is

- **Exponential Moving Average** — weighted average favoring recent closes.
- Dynamic column name: `ema_N` where N is any positive integer (e.g. `ema_12`, `ema_26`, `ema_50`).
- **Inputs:** `close` | **Outputs:** `ema_N` | **Warmup:** N bars (`warmup_for(name) = N`)
- Module default ceiling: **50** bars for batch warmup estimates

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Price > `ema_12` | Very short-term bullish | Active traders' bias line |
| Price > `ema_26` | MACD slow-line proxy | Align with positive `macd` (see `macd/README.md`) |
| Price > `ema_50` | Medium-term uptrend | Hold longs; buy dips to EMA |
| `ema_12` > `ema_26` | Short-term momentum up | Confirms MACD bullish side |
| Price crosses below `ema_26` | Momentum weakening | Reduce size or trail stops |
| Flat EMA cluster | Consolidation | Avoid trend strategies; use mean-reversion |

**Common N values:** 12, 26 (MACD), 50, 100, 200.

## How to combine

- **MACD:** Built from `ema_12` and `ema_26` internally (see `macd/README.md`).
- **SMA:** EMA for timing, SMA for regime — e.g. price > `sma_200` and pullback to `ema_20` (see `sma/README.md`).
- **Supertrend:** Both trend-following; supertrend flips on ATR breaks (see `supertrend/README.md`).
- **Recipe:** `trend_pack` includes `ema_12`, `ema_26`.

## Caveats

- Still lagging, just less than SMA — false breaks common in chop.
- Different N choices change signals; do not optimize blindly on history.
- Not a standalone signal; combine with volume and volatility context.

## Market notes

- **A — Generic daily equities:** EMA12/26 standard for daily MACD; EMA50 popular for swing entries.
- **B — India (NSE/BSE):** Works well on liquid F&O names; thin books can pierce EMA intraday then recover — daily close matters.
- **C — US equities:** Growth/tech names respect EMA21/50 on daily charts in trends; biotech can slice through EMAs on trial news.

## In this codebase

- Path: `indicators/ema/ema.py`
- Feature pattern: `ema_N` (e.g. `ema_12`, `ema_26`, `ema_50`)
- Used in recipes: `trend_pack`, `full_ta`
