"""Logistic regression model (binary label from sign of y)."""

from __future__ import annotations

NAME = "logistic_regression"
ALIASES = ("logistic_regression", "logistic")


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    labels = [1 if v > 0 else 0 for v in y]
    model = LogisticRegression(max_iter=500)
    arr = np.array(X)
    model.fit(arr, labels)
    proba = model.predict_proba(arr)
    return [float(p[1]) for p in proba]
