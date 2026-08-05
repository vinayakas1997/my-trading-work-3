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

ANGLE_NAME = "garch"


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

    from vinu_tools.compute.risk.volatility import garch_volatility

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna().values

    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns) < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(returns)),
        }])

    conditional_vol, alpha, beta, omega = garch_volatility(returns, fit=True, time_format=time_format or "1D")

    # One-step-ahead forecast: the GARCH(1,1) recursion applied to the last
    # fitted variance/return pair — the single float 26-garch.md's spec calls
    # for ("a forecasted conditional variance (volatility) for the next
    # period"), not the full in-sample conditional-vol series.
    last_variance = float(conditional_vol[-1] ** 2) if not np.isnan(conditional_vol[-1]) else float(np.var(returns[~np.isnan(returns)], ddof=1))
    last_return = float(returns[-1])
    next_period_variance = omega + alpha * last_return**2 + beta * last_variance
    next_period_volatility = float(np.sqrt(max(next_period_variance, 1e-12)))

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(returns)),
        "next_period_volatility_forecast": next_period_volatility,
        "alpha": float(alpha),
        "beta": float(beta),
        "omega": float(omega),
        "persistence": float(alpha + beta),
    }

    return pd.DataFrame([result])
