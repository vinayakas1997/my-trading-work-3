# Lasso Regression

## Why use it

- **L1 regularization** — drives weak feature coefficients to zero (automatic feature selection).
- Identify which few indicators matter from a large set (`full_ta`, `alpha158`).
- Sparse, interpretable models when you suspect only a handful of features carry signal.

## What it is

- **Lasso regression** (`sklearn.linear_model.Lasso`, `max_iter=2000`).
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `lasso` | **Aliases:** `lasso`

## How to use it

1. Z-score features before training
2. Request `ml_model=lasso` with wide feature recipes
3. Inspect non-zero coefficients after fit (external sklearn access) — surviving features are selected
4. If too many features dropped, try `elastic_net` or `ridge`

**When to pick Lasso:**

| Situation | Choice |
|---|---|
| Feature selection from 31–158 columns | Lasso |
| Suspect sparse true signal | Lasso |
| All features should contribute slightly | Ridge instead |

## Caveats

- Unstable feature selection when features are highly correlated (picks one arbitrarily).
- In-sample v1 scoring — validate OOS before trusting selected features.
- May underfit if alpha too strong — tune in research environment.
- Not a standalone trade signal.

## Market notes

- **A — Generic daily equities:** Useful for "which TA matters?" exploratory research.
- **B — India (NSE/BSE):** Sparse models reduce overfit on short NSE histories.
- **C — US equities:** Lasso on alpha158 common in factor pruning exercises.

## In this codebase

- Path: `ml_models/lasso/lasso.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
