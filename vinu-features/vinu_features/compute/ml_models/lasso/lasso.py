"""Lasso regression model."""

from __future__ import annotations

NAME = "lasso"
ALIASES = ("lasso",)


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import numpy as np
        from sklearn.linear_model import Lasso
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    model = Lasso(max_iter=2000)
    arr = np.array(X)
    model.fit(arr, y)
    return model.predict(arr).tolist()
