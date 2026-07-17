# Linear Regression

## Why use it

- **Simplest ML baseline** — interpretable linear relationship between features and forward return.
- Benchmark before trying complex models; coefficients show feature direction and relative weight.
- Fast to train; good sanity check that labels correlate with something in X.

## What it is

- **Ordinary least squares** regressor (`sklearn.linear_model.LinearRegression`).
- **Input:** feature matrix X, target y (from `labels/`)
- **Output:** in-sample predicted return per row → written as `ml_score` in `scores.parquet`
- **Model name:** `linear_regression` | **Aliases:** `linear`

## How to use it

1. Request features (`full_ta` or `alpha158`) + `ml_model=linear_regression` + `ml_label=forward_return_5`
2. Positive `ml_score` → model predicts upward forward return from feature snapshot
3. Read coefficients (externally via sklearn) for factor attribution
4. Compare R² / IC against `ridge` and `xgboost` on holdout data

**When to pick linear:**

| Situation | Choice |
|---|---|
| First model on new feature set | Linear baseline |
| Need interpretable weights | Linear or Ridge |
| Suspected non-linear interactions | Use boosting instead |

## Caveats

- Overfits easily with many correlated features (`full_ta`, alphas) — prefer `ridge` or feature selection.
- v1 `score()` trains and predicts in-sample only — not valid OOS without pipeline changes.
- Multicollinearity among SMA/MACD/RSI columns inflates coefficient variance.
- Not a standalone trade signal — threshold `ml_score` and add risk management.

## Market notes

- **A — Generic daily equities:** Academic baseline for factor regression.
- **B — India (NSE/BSE):** Works on index constituents with z-scored features; penny stocks violate linear assumptions.
- **C — US equities:** Factor regression standard in Barra-style attribution (simplified here).

## In this codebase

- Path: `ml_models/linear_regression/linear_regression.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
