# XGBoost

## Why use it

- **High-performance gradient boosting** — often best tabular model for factor + TA feature matrices.
- Captures non-linear interactions (e.g. RSI regime × volume) without hand engineering.
- Industry standard for quant ML on daily alpha features (`alpha158`, `alpha101`).

## What it is

- **XGBoost regressor** (`xgboost.XGBRegressor`).
- **Hyperparameters (fixed in code):** `n_estimators=50`, `max_depth=5`, `verbosity=0`
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `xgboost` | **Aliases:** `xgboost`

## How to use it

1. Request `alpha158` or `alpha360` + `ml_model=xgboost` + `ml_label=forward_return_5`
2. Higher `ml_score` → model predicts larger positive forward return (rank stocks by score)
3. Use feature importance / SHAP (external) to validate economic sense
4. Compare against `lightgbm` and `ridge` baseline on same data split

**Typical quant workflow:**

```
features (alpha158) → train xgboost → rank ml_score cross-sectionally → long top decile
```

## Caveats

- High overfitting risk on `alpha360` (360 cols) with short history — use regularization tuning in research.
- v1 fits in-sample — walk-forward mandatory before live use.
- Requires `pip install -e ".[ml]"` with xgboost installed.
- Not a standalone signal — combine with liquidity filters and risk limits.

## Market notes

- **A — Generic daily equities:** Default choice for tabular alpha research.
- **B — India (NSE/BSE):** Apply liquidity/price filters; boosters overfit illiquid NSE small caps easily.
- **C — US equities:** Standard in buy-side factor ML; watch survivorship in training universes.

## In this codebase

- Path: `ml_models/xgboost/xgboost.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
