# Random Forest

## Why use it

- **Non-linear baseline** without boosting complexity — captures feature interactions and thresholds.
- Robust to outliers and mixed feature scales (no z-score required).
- Feature importance scores show which indicators drive predictions.

## What it is

- **Random Forest regressor** (`sklearn.ensemble.RandomForestRegressor`).
- **Hyperparameters (fixed in code):** `n_estimators=50`, `max_depth=5`, `random_state=42`
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `random_forest` | **Aliases:** `random_forest`, `rf`

## How to use it

1. Pair with `full_ta` or `alpha158` feature recipes
2. Compare IC/R² vs `linear_regression` — if RF wins, non-linear effects matter
3. Use feature importances to prune dead columns before trying `xgboost`
4. If RF ≈ XGBoost, prefer RF for simplicity in v1 experiments

**When to pick Random Forest:**

| Situation | Choice |
|---|---|
| First non-linear model | Random Forest |
| Need feature importance | RF or boosting |
| Maximum predictive power | `xgboost` / `lightgbm` |

## Caveats

- Shallow depth (5) limits complexity — may underfit rich alpha sets.
- In-sample v1 training — overfitting still possible on wide X.
- Slower than linear on very wide matrices vs LightGBM.
- Not a standalone trade signal.

## Market notes

- **A — Generic daily equities:** Solid tabular default before gradient boosting.
- **B — India (NSE/BSE):** Handles non-linear TA interactions on Nifty 200 universes.
- **C — US equities:** Common sklearn benchmark in factor ML papers.

## In this codebase

- Path: `ml_models/random_forest/random_forest.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
