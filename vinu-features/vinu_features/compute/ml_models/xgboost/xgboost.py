"""XGBoost regression model."""

from __future__ import annotations

NAME = "xgboost"
ALIASES = ("xgboost",)


def score(X: list[list[float]], y: list[float]) -> list[float]:
    try:
        import numpy as np
        import xgboost as xgb
    except ImportError as exc:
        raise ImportError("Install ml extras: pip install -e '.[ml]'") from exc
    model = xgb.XGBRegressor(n_estimators=50, max_depth=5, verbosity=0)
    arr = np.array(X)
    model.fit(arr, y)
    return model.predict(arr).tolist()
