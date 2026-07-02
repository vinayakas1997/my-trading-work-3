# VWAP

## Why use it

- Fair-value anchor: average price paid weighted by volume — institutional benchmark.
- Judge if current price is rich or cheap vs where the market has transacted.
- On daily series here, cumulative VWAP tracks session-average cost basis over the loaded history.

## What it is

- **Volume-Weighted Average Price** — cumulative Σ(typical price × volume) / Σ(volume).
- Typical price = (high + low + close) / 3 per bar.
- **Inputs:** `high`, `low`, `close`, `volume` | **Outputs:** `vwap` | **Warmup:** 1 bar
- **Note:** This implementation is cumulative over the input row series (not reset daily per session).

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Close > `vwap` | Price above volume-weighted average | Bullish intraday/session bias (context dependent) |
| Close < `vwap` | Price below average paid | Bearish bias; resistance at VWAP |
| Pullback to `vwap` in uptrend | Retest of fair value | Buy-the-dip zone for active traders |
| Rejection at `vwap` | Sellers defending average | Short-term fade or exit longs |
| Distance from VWAP expanding | One-sided move | Mean-revert risk increases |

## How to combine

- **Volume ratio:** Reclaim VWAP on `volume_ratio_20` > 1.5 → strong reversal (see `volume_ratio/README.md`).
- **CMF:** Price above VWAP + `cmf_20` > 0 → accumulation above fair value (see `chaikin_money_flow/README.md`).
- **Alpha360:** VWAP history embedded in lag features (see `bigger_recipe/alpha360/README.md`).
- **Recipe:** `full_ta`, `alpha360`.

## Caveats

- Daily cumulative VWAP ≠ intraday session VWAP reset at open — interpret in context of your data window.
- Not a standalone signal on multi-month histories without session resets.
- Thin volume days move VWAP slowly — less meaningful on illiquid names.

## Market notes

- **A — Generic daily equities:** Traders often use session VWAP intraday; this column is cumulative over your parquet window.
- **B — India (NSE/BSE):** VWAP orders common in institutional execution on NSE; daily cumulative useful for multi-day fair value on trends.
- **C — US equities:** Session VWAP is standard for US day traders; for daily backtests, use as relative fair-value line within the loaded series.

## In this codebase

- Path: `indicators/vwap/vwap.py`
- Feature name: `vwap`
- Also included in: `full_ta`, `alpha360` (lagged VWAP columns)
