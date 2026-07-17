# Logistic Regression

## Why use it

- Predict **probability of positive forward return** instead of return magnitude.
- Natural for binary decisions: trade long if P(up) > threshold (e.g. 0.55).
- Handles class imbalance awareness when most small moves cluster near zero.

## What it is

- **Logistic regression** (`sklearn.linear_model.LogisticRegression`, `max_iter=500`).
- Converts y to binary: `1 if y > 0 else 0` from forward return labels.
- **Output:** P(y > 0) per row → `ml_score` in `scores.parquet` (probability, not return)
- **Model name:** `logistic_regression` | **Aliases:** `logistic`

## How to use it

1. Set `ml_label=forward_return_1` or `forward_return_5`
2. `ml_score` ≈ 0.5 → coin flip; > 0.55–0.60 → bullish edge (heuristic threshold)
3. Z-score features recommended for stable convergence
4. Compare calibration vs regression models on same features

**Reading `ml_score`:**

| ml_score | Interpretation |
|---|---|
| > 0.60 | Model favors positive forward return |
| 0.45–0.55 | Uncertain |
| < 0.40 | Model favors negative forward return |

## Caveats

- Discards magnitude — +0.1% and +10% both label as 1.
- Class imbalance (many small moves) can bias toward 0.5 — check base rate.
- In-sample probability estimates are overconfident without calibration split.
- Not a standalone signal — set threshold, position size, and stops.

## Market notes

- **A — Generic daily equities:** Directional classification baseline for daily bars.
- **B — India (NSE/BSE):** Circuit-up days create rare large positive labels — watch imbalance.
- **C — US equities:** Earnings create fat tails — binary label loses information vs regression.

## In this codebase

- Path: `ml_models/logistic_regression/logistic_regression.py`
- Install: `pip install -e ".[ml]"`
- Pipeline: `ml_models/runner.py`
