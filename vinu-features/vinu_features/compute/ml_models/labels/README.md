# Labels (ML targets)

## Why use it

- Define **what the model is trying to predict** — forward returns are the standard quant label.
- Separate feature engineering (indicators/recipes) from supervised target construction.
- Required step before any `ml_model` run in the worker pipeline.

## What it is

- **Label generation** for ML models — builds target column from future closes.
- **Outputs (by label name):**
  - `forward_return_1` / `fwd_ret_1` / `label` — 1-bar ahead return
  - `forward_return_5` — 5-bar ahead return
- Formula: `(close_{t+n} − close_t) / close_t`

## How to use it

1. Choose horizon: **1-day** (short-term) vs **5-day** (swing) forward return.
2. Set `ml_label` on API/CLI request to `forward_return_1` or `forward_return_5`.
3. Worker calls `build_label_column()` in `runner.py` after `features.parquet` is written.
4. Rows near series end have `None` labels (no future data) — automatically excluded from training.

**Interpretation:**

| Label | Trader meaning |
|---|---|
| `forward_return_1` | Predict tomorrow's % move |
| `forward_return_5` | Predict next week's cumulative % move |

## How to combine

- **Features:** `full_ta`, `alpha158`, or `alpha360` as X matrix
- **Models:** Regressors (`xgboost`, `ridge`) predict continuous return; `logistic_regression` binarizes sign(y)
- **Normalize:** Z-score features before linear models (see `normalize/README.md`)

## Caveats

- **Label leakage:** Never include future data in features; labels use `t+n` closes only.
- In-sample training in v1 `score()` fits and predicts same slice — research only, not production OOS.
- Corporate actions must be adjusted in close prices for valid forward returns.
- Not a trading signal by itself — model output (`ml_score`) needs threshold and risk rules.

## Market notes

- **A — Generic daily equities:** 1-day labels noisy; 5-day slightly smoother for daily bars.
- **B — India (NSE/BSE):** T+1 settlement does not change close-to-close label math; watch circuit days capping realized forward return.
- **C — US equities:** Overnight gap risk is embedded in 1-day forward return; event days dominate label variance.

## In this codebase

- Path: `ml_models/labels/labels.py`
- Aliases: `forward_return_1`, `fwd_ret_1`, `label`, `forward_return_5`
- Pipeline: `ml_models/runner.py` → `build_label_column()`
