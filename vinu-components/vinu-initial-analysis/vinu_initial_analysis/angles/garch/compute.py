"""Standalone GARCH(1,1) volatility forecast — method 26 of the 32-method plan.

See ../shock_personality/compute.py's `_compute_vol_persistence` — that
angle already fits GARCH internally for its own vol_persistence field.
This angle reuses the exact same vinu_tools.compute.risk.volatility
.garch_volatility function rather than reimplementing GARCH a second
time; the difference is this angle treats the fit itself (and the
forecasted next-period volatility) as the first-class result, per
26-garch.md's "Output format": "a forecasted conditional variance
(volatility) for the next period — a single float."
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "garch"
# Decided value, 04-enhancement-of-each-angle/08-garch.md — raised from
# the code's floor of 20, same consistency move as every other classical
# angle (ARIMA/DLinear/exponential_smoothing). Overridable via
# VINU_GARCH_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)


def _fit_and_forecast(returns: np.ndarray, time_format: str | None) -> dict[str, Any]:
    """Fits GARCH(1,1) fresh on `returns` (via the real, shared
    vinu_tools.compute.risk.volatility.garch_volatility -- the same
    function shock_personality already uses internally) and forecasts one
    step past the end. Returns every result field except symbol/
    analysis_at/angle (callers attach those). Shared by compute() and the
    walk-forward backtest (backtest.py).
    """
    from vinu_tools.compute.risk.volatility import annualization_factor, garch_volatility

    conditional_vol, alpha, beta, omega = garch_volatility(returns, fit=True, time_format=time_format or "1D")

    # garch_volatility's own conditional_vol series is ANNUALIZED
    # (internally: sqrt(variance_per_period * annualization_factor)) --
    # confirmed by reading its source. The GARCH(1,1) recursion itself
    # (omega + alpha*return^2 + beta*last_variance) operates on
    # PER-PERIOD variance, the same units as omega/alpha*return^2 and the
    # same units realized_variance (actual_next_return**2) naturally is.
    # Squaring the annualized conditional_vol back without de-annualizing
    # first mixes per-period and annualized units, inflating the forecast
    # by a factor of `af` (252x for daily data) -- a real bug, found via
    # the walk-forward backtest's real-data check (the forecast came back
    # ~5 orders of magnitude larger than the realized variance). Fixed by
    # dividing back out by the same annualization factor before feeding
    # it into the recursion.
    af = annualization_factor(time_format or "1D")
    last_variance = (
        float((conditional_vol[-1] ** 2) / af)
        if not np.isnan(conditional_vol[-1])
        else float(np.var(returns[~np.isnan(returns)], ddof=1))
    )
    last_return = float(returns[-1])
    next_period_variance = omega + alpha * last_return**2 + beta * last_variance
    next_period_volatility = float(np.sqrt(max(next_period_variance, 1e-12)))

    return {
        "status": "ok",
        "n_observations": int(len(returns)),
        "next_period_volatility_forecast": next_period_volatility,
        "next_period_variance_forecast": float(max(next_period_variance, 1e-12)),
        "alpha": float(alpha),
        "beta": float(beta),
        "omega": float(omega),
        "persistence": float(alpha + beta),
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

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna().values

    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(returns)),
        }])

    fields = _fit_and_forecast(returns, time_format)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **fields,
    }
    return pd.DataFrame([result])
