# Bollinger Bands

## Why use it

- Visualize volatility envelope around a moving average — squeeze and expansion cycles.
- Mean-reversion: fade touches of outer bands in ranges.
- Breakout: close outside bands with volume can signal trend acceleration (momentum context).

## What it is

- **Bollinger Bands** — middle band = SMA(20); upper/lower = middle ± 2 standard deviations of close.
- **Inputs:** `close` | **Outputs:** `bb_upper`, `bb_mid`, `bb_lower` | **Warmup:** 21 bars
- Period: **20** | Std dev multiplier: **2.0**

## How to read it

| Zone / signal | Meaning | Typical use |
|---|---|---|
| Close at `bb_upper` | Price at +2σ — stretched high | Fade in range; caution chasing in trend |
| Close at `bb_lower` | Price at −2σ — stretched low | Buy bounce in range with confirmation |
| Close > `bb_upper` | Breakout above envelope | Momentum long if volume confirms |
| Close < `bb_lower` | Breakdown below envelope | Momentum short or exit longs |
| Bands narrowing (squeeze) | Low volatility | Prepare for expansion — direction from breakout |
| `bb_mid` slope up | Bullish mean drift | Pullbacks to mid-band as support |

## How to combine

- **RSI / Stochastic:** Touch `bb_lower` + oversold oscillator → mean-reversion long (see `rsi/README.md`, `stochastic/README.md`).
- **Volume:** Band walk on rising `volume_ratio_20` → trend continuation (see `volume_ratio/README.md`).
- **ATR:** Confirm squeeze when both bands tight and `atr_14` low (see `atr/README.md`).
- **Recipe:** `volatility_pack`, `mean_reversion_pack`, `full_ta`.

## Caveats

- Strong trends "ride the upper band" — fading upper band loses money in momentum regimes.
- Not a standalone signal; band touch without oscillator/volume context is weak.
- 2σ assumes roughly normal returns — fat tails break the model on event days.

## Market notes

- **A — Generic daily equities:** Classic 20,2 on daily; squeeze setups popular on indices and liquid names.
- **B — India (NSE/BSE):** Upper circuit sequences hug upper band for days; mean-reversion fails until circuit policy allows normal trading.
- **C — US equities:** Index products show cleaner band behavior than small caps; earnings gaps pierce bands instantly.

## In this codebase

- Path: `indicators/bollinger/bollinger.py`
- Feature names: `bb_upper`, `bb_mid`, `bb_lower`
- Also included in: `volatility_pack`, `mean_reversion_pack`, `full_ta`
