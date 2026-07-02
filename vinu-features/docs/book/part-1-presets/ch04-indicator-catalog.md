# Chapter 4 — Indicator Catalog (modular)

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/compute/indicators/` |
| **Status** | v1 modular |

## Layout

One folder per indicator: `rsi/rsi.py`, `sma/sma.py`, etc.

## Implemented indicators

| Folder | Columns |
|--------|---------|
| sma | `sma_N` |
| rsi | `rsi_14` |
| ema | `ema_N` |
| macd | `macd` |
| macd_signal | `macd_signal` |
| daily_return | `daily_return` |
| volatility_20d | `volatility_20d` |
| atr | `atr_14` |
| bollinger | `bb_upper`, `bb_mid`, `bb_lower` |
| stochastic | `stoch_k`, `stoch_d` |
| obv | `obv` |
| vwap | `vwap` |
| volume_ratio | `volume_ratio_20` |
| high_low_spread | `high_low_spread` |
| open_close_return | `open_close_return` |
| momentum_n | `momentum_10` |
| roc | `roc_12` |
| cci | `cci_20` |
| williams_r | `williams_r_14` |
| adx | `adx_14` |
| supertrend | `supertrend` |
| chaikin_money_flow | `cmf_20` |
| aroon | `aroon_up`, `aroon_down` |

Dispatch: [`compute/registry.py`](../../../vinu_features/compute/registry.py)

## Feature specs

List indicators and params: `vinu-features features list` / `features help rsi`

See [ch08-feature-specs.md](ch08-feature-specs.md).
