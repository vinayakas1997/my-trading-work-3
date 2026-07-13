# Ridge Regression

## Why use it

- Linear model with **L2 regularization** — handles correlated TA/alpha features better than plain linear.
- Stable coefficients when `full_ta` (31 cols) or `alpha158` (158 cols) have multicollinearity.
- Still interpretable — good middle ground before black-box boosters.

## What it is

- **Ridge regression** (`sklearn.linear_model.Ridge`, default alpha).
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `ridge` | **Aliases:** `ridge`

## How to use it

1. Z-score features recommended (see `normalize/README.md`)
2. Use with `alpha158` or `full_ta` when many correlated columns
3. Compare to `linear_regression` — if Ridge improves stability but similar IC, prefer Ridge
4. Escalate to `lasso` if you want sparse feature selection

**When to pick Ridge:**

| Situation | Choice |
|---|---|
| Many correlated indicators | Ridge |
| Need all features shrunk, not dropped | Ridge |
| Want sparse model | Lasso or ElasticNet |

## Caveats

- Still linear — cannot capture interaction effects (e.g. RSI × volume).
- In-sample fit in v1 — walk-forward validation required for real research.
- Default sklearn alpha may need tuning for your universe.
- Not a standalone trading signal.

## Market notes

- **A — Generic daily equities:** Standard regularized factor regression.
- **B — India (NSE/BSE):** Regularization helps when NSE features are noisy on small caps.
- **C — US equities:** Common baseline in quant factor studies before gradient boosting.

## In this codebase

- Path: `ml_models/ridge/ridge.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
