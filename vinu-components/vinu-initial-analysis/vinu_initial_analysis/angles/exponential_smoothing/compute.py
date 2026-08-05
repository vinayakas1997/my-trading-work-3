"""Exponential smoothing classical baseline — method 28 of the 32-method
plan.

See New-talk-/Final-implementation/01-present-considerations/28-exponential-smoothing.md:
computes a forecast as a weighted average of past observations with
exponentially-decaying weights; simple variants handle level only,
extended (double/Holt) variants add a trend component. The spec's output
format is "a point forecast ... optionally decomposed into level/trend/
seasonal components for the Holt-Winters variant" — we fit Holt's linear
trend method (double exponential smoothing: level + trend, no
seasonality — daily-bar stock series have no reliable fixed seasonal
period) and report both the one-step-ahead forecast and the fitted
level/trend decomposition.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "exponential_smoothing"
_MIN_OBSERVATIONS = 10


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "angle": ANGLE_NAME,
            "status": "no_data",
        }])

    analysis_at = datetime.now(timezone.utc).isoformat()
    close = bars["close"].astype(float).dropna().values

    if len(close) < _MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(close)),
        }])

    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = ExponentialSmoothing(
                close, trend="add", seasonal=None, initialization_method="estimated"
            )
            res = model.fit()
        point_forecast = float(res.forecast(1)[0])
    except Exception:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "fit_failed",
            "n_observations": int(len(close)),
        }])

    smoothing_level = float(res.params.get("smoothing_level", np.nan))
    smoothing_trend = float(res.params.get("smoothing_trend", np.nan))
    fitted_level = float(res.level[-1])
    fitted_trend = float(res.trend[-1]) if res.trend is not None else None

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(close)),
        "forecast": point_forecast,
        "alpha": smoothing_level,
        "beta": smoothing_trend,
        "level": fitted_level,
        "trend": fitted_trend,
        "sse": float(res.sse),
    }

    return pd.DataFrame([result])
