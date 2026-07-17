# Chapter 5 — ML Models

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/compute/ml_models/` |

## Folders

| Model | Folder |
|-------|--------|
| labels | `labels/` |
| normalize | `normalize/` |
| linear_regression | `linear_regression/linear_regression.py` |
| ridge | `ridge/ridge.py` |
| lasso | `lasso/lasso.py` |
| elastic_net | `elastic_net/elastic_net.py` |
| logistic_regression | `logistic_regression/logistic_regression.py` |
| random_forest | `random_forest/random_forest.py` |
| lightgbm | `lightgbm/lightgbm.py` |
| xgboost | `xgboost/xgboost.py` |
| catboost | `catboost/catboost.py` |

Dispatch: [`registry.py`](../../../vinu_features/compute/ml_models/registry.py) — orchestration: [`runner.py`](../../../vinu_features/compute/ml_models/runner.py)

Install: `pip install -e ".[ml]"`

Future plan: [`future_implementation_plan.md`](../../../vinu_features/compute/ml_models/future_implementation_plan.md)

Optional request fields: `ml_model`, `ml_label` → writes `scores.parquet`.
