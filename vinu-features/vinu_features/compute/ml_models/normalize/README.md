# Normalize (z-score)

## Why use it

- Put features on comparable scale — required for linear models and helpful for interpretation.
- Cross-sectional research: z-score each feature across symbols on a given day (apply in your research layer).
- Reduce dominance of large-magnitude columns (e.g. `obv` vs `rsi_14`) in distance-based models.

## What it is

- **Z-score normalization** — `(x − mean) / std` per column over the provided value list.
- Function: `zscore_column(values)` — returns normalized series with `None` preserved.
- Not a registered `ml_model` — utility for preprocessing.

## How to use it

1. After computing features, z-score each column before `linear_regression`, `ridge`, `lasso`, `elastic_net`.
2. Tree models (`xgboost`, `lightgbm`, `random_forest`, `catboost`) are scale-invariant — normalization optional.
3. For universe runs: z-score **per date across stocks** (cross-sectional) in downstream research code.

**When required vs optional:**

| Model type | Z-score |
|---|---|
| Linear / Ridge / Lasso / ElasticNet | Recommended |
| Logistic regression | Recommended |
| Tree / boosting | Optional |

## Caveats

- In-sample mean/std from full series leaks future info in backtests — use rolling or train-set-only stats in production research.
- v1 helper normalizes one column at a time over all rows passed — not automatic in `runner.py`.
- Constant columns (std=0) divide by 1.0 fallback — check for dead features.

## Market notes

- **A — Generic daily equities:** Standard preprocessing in quant pipelines.
- **B — India (NSE/BSE):** Cross-sectional z-score on Nifty 500 reduces sector size bias.
- **C — US equities:** Winsorize extremes before z-score when micro-cap noise is high.

## In this codebase

- Path: `ml_models/normalize/normalize.py`
- Function: `zscore_column()`
