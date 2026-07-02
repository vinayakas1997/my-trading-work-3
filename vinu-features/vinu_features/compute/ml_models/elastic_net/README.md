# Elastic Net

## Why use it

- **Combines L1 + L2** — feature selection (Lasso-like) with correlated-feature stability (Ridge-like).
- Best when you want sparsity but features are grouped (e.g. Bollinger upper/mid/lower).
- Practical default linear model for wide alpha feature matrices.

## What it is

- **Elastic Net** (`sklearn.linear_model.ElasticNet`, `max_iter=2000`).
- **Input:** X, y | **Output:** predicted forward return (`ml_score`)
- **Model name:** `elastic_net` | **Aliases:** `elastic_net`

## How to use it

1. Z-score features (recommended)
2. Use with `alpha158` or `alpha101` when Lasso alone is unstable
3. Compare coefficient sparsity vs `lasso` and coefficient stability vs `ridge`
4. Escalate to `xgboost` if non-linear lift is needed

**When to pick Elastic Net:**

| Situation | Choice |
|---|---|
| Wide correlated feature set | Elastic Net |
| Lasso too unstable, Ridge too dense | Elastic Net |
| Pure interpretation | Ridge or Lasso alone |

## Caveats

- Two hyperparameters (alpha, l1_ratio) — defaults may not suit all universes.
- Still linear — no interaction terms.
- In-sample v1 fit only.
- Not a standalone trading signal.

## Market notes

- **A — Generic daily equities:** Workhorse linear model for multi-factor panels.
- **B — India (NSE/BSE):** Helps when indicator groups correlate on index-heavy universes.
- **C — US equities:** Standard sklearn choice for regularized factor regression.

## In this codebase

- Path: `ml_models/elastic_net/elastic_net.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
