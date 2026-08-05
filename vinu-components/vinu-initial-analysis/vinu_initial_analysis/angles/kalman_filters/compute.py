"""Kalman filter classical state-estimation baseline — method 27 of the
32-method plan.

See New-talk-/Final-implementation/01-present-considerations/27-kalman-filters.md:
recursively estimates a hidden state (the "true" underlying price level and
its local trend) from noisy observations via a predict-then-correct cycle.
This is an estimate of the present/recent state, not a forward forecast —
the spec explicitly calls that out.

Implemented via statsmodels' local-linear-trend structural time series
model (`UnobservedComponents`), which is exactly a two-state (level, trend)
Kalman filter/smoother with maximum-likelihood-fitted noise variances —
the same predict/update recursion a hand-rolled Kalman filter would run,
without reimplementing the recursion and its likelihood-based variance
fitting by hand.
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "kalman_filters"
_MIN_OBSERVATIONS = 20


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

    from statsmodels.tsa.statespace.structural import UnobservedComponents

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = UnobservedComponents(close, level="local linear trend")
            res = model.fit(disp=False)
    except Exception:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "fit_failed",
            "n_observations": int(len(close)),
        }])

    # filtered_state: [level, trend] rows x n_observations columns — the
    # recursive predict-then-correct state estimate at each timestep, per
    # 27-kalman-filters.md's "processed sequentially/online" description.
    # We report the terminal (most recent) filtered state as "the" present
    # state estimate, plus its covariance as the uncertainty the spec asks
    # for.
    filtered_level = float(res.filtered_state[0, -1])
    filtered_trend = float(res.filtered_state[1, -1])
    level_variance = float(res.filtered_state_cov[0, 0, -1])
    trend_variance = float(res.filtered_state_cov[1, 1, -1])
    level_std = float(np.sqrt(max(level_variance, 0.0)))
    trend_std = float(np.sqrt(max(trend_variance, 0.0)))

    # Smoothed (two-pass, uses the whole series) estimate of the same
    # terminal state, for comparison against the online-filtered value.
    smoothed_level = float(res.smoothed_state[0, -1])
    smoothed_trend = float(res.smoothed_state[1, -1])

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(close)),
        "filtered_level": filtered_level,
        "filtered_level_std": level_std,
        "filtered_trend": filtered_trend,
        "filtered_trend_std": trend_std,
        "smoothed_level": smoothed_level,
        "smoothed_trend": smoothed_trend,
        "last_observed_close": float(close[-1]),
    }

    return pd.DataFrame([result])
