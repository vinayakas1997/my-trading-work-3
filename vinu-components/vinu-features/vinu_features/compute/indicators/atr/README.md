# ATR (Average True Range)

## Why use it

- Measure how much a stock typically moves per bar — essential for stop-loss and position sizing.
- Normalize risk across symbols (₹10 ATR on a ₹100 stock vs ₹500 stock).
- Feed volatility-adjusted systems (supertrend, trailing stops, breakout filters).

## What it is

- **Average True Range** — smoothed average of true range (max of high−low, |high−prev_close|, |low−prev_close|).
- Absolute price units (not percent); higher = more volatile.
- **Inputs:** `high`, `low`, `close` | **Outputs:** `atr_14` | **Warmup:** 15 bars
- Period: **14** (fixed in code)

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Rising `atr_14` | Volatility expanding | Widen stops; reduce position size |
| Falling `atr_14` | Volatility compressing | Tighter stops; breakout may be near |
| ATR at multi-week low | Squeeze / coiling | Watch for range expansion (direction TBD) |
| ATR spike | Event bar (news, gap) | Do not use normal 1×ATR stop that day |
| Stop = entry − 2×ATR | Classic chandelier-style risk | Volatility-scaled exit |

**Rule of thumb:** Risk per share ≈ 1.5–2.5 × `atr_14` for swing stops (heuristic, not guaranteed).

## How to combine

- **Supertrend:** Built on `atr_14` × 3 (see `supertrend/README.md`).
- **Bollinger:** Both measure vol — band width expands when ATR rises (see `bollinger/README.md`).
- **ADX:** High ADX + rising ATR = strong trending volatile move (see `adx/README.md`).
- **Recipe:** `volatility_pack`, `full_ta`.

## Caveats

- Absolute units — compare ATR/price ratio for cross-stock comparison.
- Lagging; spikes persist in the average after the event.
- Not a directional signal — use with trend tools for bias.

## Market notes

- **A — Generic daily equities:** Standard 14-period on daily bars; scale stops to account size.
- **B — India (NSE/BSE):** Circuit days and budget/event gaps inflate ATR for weeks; F&O traders use ATR for strike spacing intuition.
- **C — US equities:** Earnings can double ATR overnight; options implied vol often leads cash ATR.

## In this codebase

- Path: `indicators/atr/atr.py`
- Feature name: `atr_14`
- Also included in: `volatility_pack`, `full_ta`
