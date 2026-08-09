"""ARIMA classical statistical baseline — method 25 of the 32-method plan.

See New-talk-/Final-implementation/01-present-considerations/25-arima.md:
fits an autoregressive + integrated + moving-average model to the price
series (a parametric statistical model, no pretraining, fit fresh per
series) and reports its "standard statistical output shape": a point
forecast plus a confidence interval.

Order (p, d, q) is chosen by a small grid search over AIC rather than a
single fixed order, since the spec has no fixed lookback window and asks
for a genuine fit against "whatever history is chosen".
"""

from __future__ import annotations

import warnings
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "arima"

# Small, cheap grid — real ARIMA fit but bounded so this stays fast for the
# runner and for tests. d=1 covers the typical non-stationary price series;
# d=0 is included in case the input is already stationary (e.g. returns).
_ORDER_GRID = [
    (p, d, q)
    for d in (0, 1)
    for p in (0, 1, 2)
    for q in (0, 1, 2)
    if not (p == 0 and q == 0)
]

# decided value, 04-enhancement-of-each-angle/01-arima.md — raised from
# 30. Overridable via VINU_ARIMA_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
# NOTE: backtest.py has its own separate MIN_OBSERVATIONS constant (not
# imported from here) -- update both together, same env var covers both.
_MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)


def _fit_best_arima(close: np.ndarray):
    """Grid-search (p, d, q) by AIC, returning the best fitted results object."""
    from statsmodels.tsa.arima.model import ARIMA

    best_res = None
    best_aic = np.inf
    best_order = None
    for order in _ORDER_GRID:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(close, order=order)
                res = model.fit()
            if np.isfinite(res.aic) and res.aic < best_aic:
                best_aic = res.aic
                best_res = res
                best_order = order
        except Exception:
            continue
    return best_res, best_order


def _forecast_fields(res, order: tuple[int, int, int], n_observations: int) -> dict[str, Any]:
    """Extracts the standard result fields from a fitted ARIMA results object.

    Shared by compute() and the walk-forward backtest (angles/arima/backtest.py)
    so both a fresh fit and a state.append(refit=False)-extended fit produce
    the exact same output shape.
    """
    forecast_result = res.get_forecast(steps=1)
    point_forecast = float(forecast_result.predicted_mean[0])
    ci = forecast_result.conf_int(alpha=0.05)
    ci_arr = np.asarray(ci).reshape(-1)
    lower, upper = float(ci_arr[0]), float(ci_arr[1])
    return {
        "status": "ok",
        "n_observations": int(n_observations),
        "order": {"p": order[0], "d": order[1], "q": order[2]},
        "aic": float(res.aic),
        "forecast": point_forecast,
        "confidence_interval": [lower, upper],
        "confidence_level": 0.95,
    }


def _fit_and_forecast(close: np.ndarray):
    """Fits a fresh ARIMA model (AIC grid search) and forecasts one step
    past the end of `close`. Returns (fields, res): `fields` is every
    result column except symbol/analysis_at/angle (callers attach those),
    and `res` is the fitted statsmodels results object itself — exposed so
    walk-forward backtest callers (angles/arima/backtest.py) can carry it
    forward as `state` and extend it with `.append(refit=False)` on
    non-refit steps instead of re-running the grid search every time.

    Raises ValueError if no order in the grid produced a finite-AIC fit;
    callers decide how to report that.
    """
    best_res, best_order = _fit_best_arima(close)
    if best_res is None:
        raise ValueError("no ARIMA order in the grid produced a valid fit")
    fields = _forecast_fields(best_res, best_order, len(close))
    return fields, best_res


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

    try:
        fields, _res = _fit_and_forecast(close)
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
        **fields,
    }
    return pd.DataFrame([result])
