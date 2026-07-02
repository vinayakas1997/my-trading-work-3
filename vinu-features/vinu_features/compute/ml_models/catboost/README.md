# CatBoost

## Why use it

- **Gradient boosting alternative** with strong defaults and categorical support (future use).
- Another non-linear model to ensemble or benchmark against XGBoost/LightGBM.
- Often robust with minimal hyperparameter tuning on tabular financial data.

## What it is

- **CatBoost regressor** (`catboost.CatBoostRegressor`).
- **Hyperparameters (fixed in code):** `iterations=50`, `depth=5`, `verbose=False`
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `catboost` | **Aliases:** `catboost`

## How to use it

1. Same pipeline as other boosters: features + `ml_label` + `ml_model=catboost`
2. Compare OOS IC vs `xgboost` and `lightgbm` on identical splits
3. Consider ensembling average of three boosters for research stability
4. Use when LightGBM/XGBoost install or tuning is problematic (CatBoost often stable)

## Caveats

- CatBoost may require extra setup on Windows — see project `future_implementation_plan.md`.
- All numeric features in v1 — categorical sector/industry not yet wired.
- In-sample v1 fit; overfitting risk on alpha360.
- Not a standalone trade signal.

## Market notes

- **A — Generic daily equities:** Third booster in model shootouts.
- **B — India (NSE/BSE):** Test on liquid universe; verify CatBoost installs on your Windows env.
- **C — US equities:** Used in Kaggle-style tabular competitions; applicable to factor panels.

## In this codebase

- Path: `ml_models/catboost/catboost.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
