"""Ridge regression model."""

from __future__ import annotations

NAME = "ridge"
ALIASES = ("ridge",)


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import numpy as np
        from sklearn.linear_model import Ridge
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    model = Ridge()
    arr = np.array(X)
    model.fit(arr, y)
    return model.predict(arr).tolist()
