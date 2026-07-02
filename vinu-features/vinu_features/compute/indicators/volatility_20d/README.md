# Volatility (20-day)

## Why use it

- Quantify recent return variability — risk regime and position sizing input.
- Compare stocks or periods: high `volatility_20d` = choppier / riskier recent path.
- Filter strategies: reduce size or widen stops when volatility is elevated.

## What it is

- **20-day rolling standard deviation** of `daily_return` (not annualized in this column).
- Higher values = larger day-to-day swings in percentage returns.
- **Inputs:** `close` (via `daily_return`) | **Outputs:** `volatility_20d` | **Warmup:** 21 bars
- Window: **20** bars of daily returns

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Rising `volatility_20d` | Risk increasing | Cut position size; widen stops |
| Falling `volatility_20d` | Calm period | Compression — breakout watch |
| Vol near historical lows | Quiet regime | Mean-reversion may work; breakouts pending |
| Vol spike after event | Shock absorbed in window | Wait for vol to mean-revert before sizing up |
| High vol + downtrend | Stressful decline | Avoid catching falling knives |

**Cross-stock:** Compare `volatility_20d` / `daily_return` scale — or rank within universe for relative risk.

## How to combine

- **ATR:** Both vol measures — ATR in price units, this in return std (see `atr/README.md`).
- **Bollinger:** Band width correlates with rising `volatility_20d` (see `bollinger/README.md`).
- **Swing filter:** `swing_basic` pairs with `rsi_14` for risk-aware swing setups.
- **Recipe:** `swing_basic`, `volatility_pack`, `full_ta`.

## Caveats

- Backward-looking — does not predict next day's vol.
- Not annualized; do not confuse with VIX or 16√252 scaling without conversion.
- Not a standalone trading signal.

## Market notes

- **A — Generic daily equities:** Useful for universe ranking in quant screens; discretionary traders use as risk dial.
- **B — India (NSE/BSE):** Budget day, election results, and RBI policy spike vol across the index; stock-specific vol jumps on block deals and results.
- **C — US equities:** FOMC/CPI days elevate vol cluster-wide; single-name biotech vol can dominate the 20-day window for weeks.

## In this codebase

- Path: `indicators/volatility_20d/volatility_20d.py`
- Feature name: `volatility_20d`
- Also included in: `swing_basic`, `volatility_pack`, `full_ta`
