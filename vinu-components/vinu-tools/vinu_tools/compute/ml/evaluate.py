"""Evaluation interface — wraps ml_models registry + sklearn metrics."""

import numpy as np


def evaluate(y_true, y_pred) -> dict:
    """Compute Spearman IC + regression metrics.

    Returns dict with keys: ic (Spearman rank correlation),
    mse, mae, r2 (NaN if < 2 samples).
    """
    from scipy.stats import spearmanr
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)

    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    yt, yp = y_true[mask], y_pred[mask]

    n = len(yt)
    if n < 2:
        return {"ic": 0.0, "mse": float("nan"), "mae": float("nan"), "r2": float("nan")}

    ic = float(spearmanr(yt, yp)[0]) if n >= 5 else 0.0

    return {
        "ic": ic,
        "mse": float(mean_squared_error(yt, yp)),
        "mae": float(mean_absolute_error(yt, yp)),
        "r2": float(r2_score(yt, yp)) if n >= 2 else float("nan"),
    }
