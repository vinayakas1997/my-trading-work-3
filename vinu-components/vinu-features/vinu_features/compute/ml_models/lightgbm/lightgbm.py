"""LightGBM regression model."""

from __future__ import annotations

NAME = "lightgbm"
ALIASES = ("lightgbm",)


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import lightgbm as lgb
        import numpy as np
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    model = lgb.LGBMRegressor(n_estimators=50, max_depth=5, verbose=-1)
    arr = np.array(X)
    model.fit(arr, y)
    return model.predict(arr).tolist()
