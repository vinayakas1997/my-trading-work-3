# SMA (Simple Moving Average)

## Why use it

- Define the prevailing trend direction and dynamic support/resistance on daily charts.
- Filter trades: only buy above the moving average, sell below (trend-following discipline).
- Compare fast vs slow SMAs for golden/death cross regime changes.

## What it is

- **Simple Moving Average** — arithmetic mean of the last N closing prices.
- Dynamic column name: `sma_N` where N is any positive integer (e.g. `sma_20`, `sma_50`, `sma_200`).
- **Inputs:** `close` | **Outputs:** `sma_N` | **Warmup:** N bars (`warmup_for(name) = N`)
- Module default ceiling: **100** bars for batch warmup estimates

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Price > `sma_20` | Short-term bullish structure | Swing long bias; `sma_20` as trailing support |
| Price > `sma_50` | Intermediate uptrend | Pullback buys when RSI cools (see `rsi/README.md`) |
| Price > `sma_200` | Long-term bull market (classic) | Institutional "in trend" filter |
| `sma_10` > `sma_50` | Golden cross zone | Momentum alignment — bullish |
| `sma_50` < `sma_200` | Death cross zone | Bearish regime — reduce long exposure |
| Price closes below `sma_20` in uptrend | Pullback or trend break | Wait for reclaim or tighten stops |

**Common N values in recipes:** 10, 20, 50, 100, 200.

## How to combine

- **EMA:** Faster reaction with `ema_12` / `ema_26` in `trend_pack` (see `ema/README.md`).
- **MACD:** SMA slope + positive `macd` → trend with momentum (see `macd/README.md`).
- **ADX:** Price above `sma_50` and `adx_14` > 25 → trade trend, not chop (see `adx/README.md`).
- **Volatility:** Use `atr_14` for stop distance from `sma_20` (see `atr/README.md`).

## Caveats

- Lagging — SMAs react slowly; late entries and exits in fast reversals.
- Whipsaws when price oscillates around the average in ranges.
- Not a standalone signal; crossovers alone are not a full strategy.

## Market notes

- **A — Generic daily equities:** `sma_200` is the classic institutional trend line; `sma_20`/`sma_50` for swing timing.
- **B — India (NSE/BSE):** `sma_200` widely watched on Nifty 50 and large caps; circuit days can gap price far from SMA — wait for normalization.
- **C — US equities:** S&P 500 `sma_200` is a macro risk-on/risk-off gauge; single-stock SMAs break frequently around earnings.

## In this codebase

- Path: `indicators/sma/sma.py`
- Feature pattern: `sma_N` (e.g. `sma_10`, `sma_20`, `sma_50`, `sma_100`)
- Used in recipes: `basic_ta`, `swing_basic`, `momentum`, `trend_pack`, `full_ta`
