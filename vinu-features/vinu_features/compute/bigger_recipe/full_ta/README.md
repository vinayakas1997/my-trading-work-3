# full_ta

## Why use it

- **Complete standard TA feature matrix** — all 31 registry indicators in one request.
- ML and research workflows needing broad technical coverage without listing each column.
- Baseline feature set for model comparison against alpha presets.

## What it is

- **All standard TA indicators** — full dispatch bundle.
- **Recipe name:** `full_ta` | **Warmup:** 100 bars | **Feature count:** 31
- **Outputs:** `sma_5`, `sma_10`, `sma_20`, `sma_50`, `sma_100`, `ema_12`, `ema_26`, `rsi_14`, `macd`, `macd_signal`, `daily_return`, `volatility_20d`, `atr_14`, `bb_upper`, `bb_mid`, `bb_lower`, `stoch_k`, `stoch_d`, `obv`, `vwap`, `volume_ratio_20`, `high_low_spread`, `open_close_return`, `momentum_10`, `roc_12`, `cci_20`, `williams_r_14`, `adx_14`, `supertrend`, `cmf_20`, `aroon_up`, `aroon_down`

## How to use it (workflow)

**Discretionary scan order:**

1. **Regime:** `adx_14`, `sma_50`/`sma_200` proxy (`sma_100`), `supertrend`
2. **Momentum:** `macd`, `macd_signal`, `rsi_14`, `roc_12`
3. **Volatility:** `atr_14`, Bollinger bands, `volatility_20d`
4. **Volume:** `obv`, `cmf_20`, `volume_ratio_20`
5. **Mean-reversion check:** `stoch_k`, `cci_20`, `williams_r_14`

**ML workflow:** Request `full_ta` + `ml_model` (e.g. `xgboost`) + label `forward_return_5` → see `ml_models/runner.py`.

## Components

Every column maps to `indicators/{name}/README.md` — see individual indicator guides for interpretation.

## Caveats

- Heavy column count — longer compute and warmup (100 bars minimum history).
- Redundant signals across indicators — use feature selection for ML.
- Not a discretionary "read all 31" dashboard — use themed packs for focused views.

## Market notes

- **A — Generic daily equities:** Standard research baseline on daily OHLCV.
- **B — India (NSE/BSE):** Ensure corporate-action-adjusted OHLCV in source data for reliable SMA/returns.
- **C — US equities:** Full TA on ADRs may mix session effects — prefer primary listing data.

## In this codebase

- Path: `bigger_recipe/full_ta/full_ta.py`
- Request recipe: `full_ta`
