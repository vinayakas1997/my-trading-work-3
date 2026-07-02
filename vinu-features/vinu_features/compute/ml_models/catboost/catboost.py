"""CatBoost regression model."""

from __future__ import annotations

NAME = "catboost"
ALIASES = ("catboost",)


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import numpy as np
        from catboost import CatBoostRegressor
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    model = CatBoostRegressor(iterations=50, depth=5, verbose=False)
    arr = np.array(X)
    model.fit(arr, y)
    return model.predict(arr).tolist()
