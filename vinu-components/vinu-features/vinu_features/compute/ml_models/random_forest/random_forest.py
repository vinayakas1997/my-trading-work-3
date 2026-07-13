"""Random forest regression model."""

from __future__ import annotations

NAME = "random_forest"
ALIASES = ("random_forest", "rf")


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
    arr = np.array(X)
    model.fit(arr, y)
    return model.predict(arr).tolist()
