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
# Decided value, 04-enhancement-of-each-angle/10-kalman_filters.md —
# raised from 20, same consistency move as every other classical angle.
MIN_OBSERVATIONS = 100


def _fit(close: np.ndarray):
    """Fits the local-linear-trend Kalman filter/smoother fresh on
    `close`. Raises ValueError on fit failure; returns the fitted results
    object otherwise. Shared by compute() and the walk-forward backtest
    (backtest.py).
    """
    from statsmodels.tsa.statespace.structural import UnobservedComponents

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = UnobservedComponents(close, level="local linear trend")
            res = model.fit(disp=False)
    except Exception as exc:
        raise ValueError(f"kalman filter fit failed: {exc!r}") from exc
    return res


def _filtered_fields(res, n_observations: int) -> dict[str, Any]:
    """The causal (online, predict-then-correct) state only -- safe to
    use inside a walk-forward step. Never mix in `res.smoothed_state`
    here; see _smoothed_fields() and backtest.py's module docstring for
    why that would be a real look-ahead-bias bug, not a style choice.
    """
    filtered_level = float(res.filtered_state[0, -1])
    filtered_trend = float(res.filtered_state[1, -1])
    level_variance = float(res.filtered_state_cov[0, 0, -1])
    trend_variance = float(res.filtered_state_cov[1, 1, -1])
    return {
        "status": "ok",
        "n_observations": n_observations,
        "filtered_level": filtered_level,
        "filtered_level_std": float(np.sqrt(max(level_variance, 0.0))),
        "filtered_trend": filtered_trend,
        "filtered_trend_std": float(np.sqrt(max(trend_variance, 0.0))),
    }


def _smoothed_fields(res) -> dict[str, Any]:
    """The non-causal (two-pass, whole-series) terminal state -- NEVER
    used inside the walk-forward backtest, only as a separate,
    whole-history-only diagnostic (backtest.py's run_smoothed_diagnostic).
    """
    return {
        "smoothed_level": float(res.smoothed_state[0, -1]),
        "smoothed_trend": float(res.smoothed_state[1, -1]),
    }


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

    if len(close) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(close)),
        }])

    try:
        res = _fit(close)
    except ValueError:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "fit_failed",
            "n_observations": int(len(close)),
        }])

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **_filtered_fields(res, len(close)),
        **_smoothed_fields(res),
        "last_observed_close": float(close[-1]),
    }
    return pd.DataFrame([result])
