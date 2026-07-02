# LightGBM

## Why use it

- **Fast gradient boosting** — similar accuracy to XGBoost, often quicker on wide feature sets.
- Best for `alpha158` / `alpha101` with many columns and large universes.
- Leaf-wise growth can find fine-grained patterns in factor interactions.

## What it is

- **LightGBM regressor** (`lightgbm.LGBMRegressor`).
- **Hyperparameters (fixed in code):** `n_estimators=50`, `max_depth=5`, `verbose=-1`
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `lightgbm` | **Aliases:** `lightgbm`

## How to use it

1. Same workflow as `xgboost` — features + label + `ml_model=lightgbm`
2. Rank predictions cross-sectionally for long/short portfolios
3. Benchmark speed vs XGBoost on `alpha360` wide matrices
4. Use feature importance to prune redundant alpha families

**When to pick LightGBM vs XGBoost:**

| Situation | Choice |
|---|---|
| Large wide feature matrix | LightGBM (speed) |
| Maximum robustness on medium data | Try both; pick by OOS IC |
| Windows install friction | XGBoost sometimes easier |

## Caveats

- Same overfitting risks as XGBoost on high-dimensional alphas.
- In-sample v1 scoring only.
- Requires lightgbm in ML extras install.
- Not a standalone trade signal.

## Market notes

- **A — Generic daily equities:** Qlib ecosystem often pairs with LightGBM.
- **B — India (NSE/BSE):** Efficient for Nifty 500 × alpha158 daily panels.
- **C — US equities:** Common in production factor pipelines for speed.

## In this codebase

- Path: `ml_models/lightgbm/lightgbm.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
