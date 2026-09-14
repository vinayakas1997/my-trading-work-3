from __future__ import annotations

import pandas as pd

# Mirrors vinu_initial_analysis/angles/regime_analysis/compute.py's
# classify_regime() thresholding (21-day rolling vol, same 4 labels) --
# reimplemented here rather than imported across the service boundary, and
# reimplemented rather than read from that angle's stored output because
# that output is a window-aggregate (per-regime win rate/Sharpe/pct_of_time
# across the whole analyzed history), not a single "today's regime" value.
# See daily-allocation/SKILL.md for the full explanation.
#
# The vol threshold used to be `vol.quantile(0.7)` computed over the WHOLE
# input series -- a confirmed look-ahead leak (per compute.py's own
# docstring, which fixed the identical defect there first): an early bar's
# regime label depended on volatility from bars that hadn't happened yet.
# This now uses the same point-in-time-safe fix compute.py adopted: a
# rolling z-score of vol against a 120-day trailing baseline, using only
# bars up to and including "today". The return-based bull/bear thresholds
# are intentionally left as this module's own pre-existing single-day
# convention (compute.py uses a 20-day cumulative return instead) -- that
# is a separate design choice, not the leak this fix addresses.
_ROLLING_WINDOW = 21
_VOL_BASELINE_WINDOW = 120
_VOL_Z_THRESHOLD = 1.0
_ANN_FACTOR_1D = 252 ** 0.5


def _classify(ret: float, vol_z: float) -> str:
    if pd.notna(vol_z) and vol_z > _VOL_Z_THRESHOLD:
        return "high_vol"
    if ret > 0.01:
        return "bull"
    if ret < -0.01:
        return "bear"
    return "sideways"


def classify_current_regime(returns: pd.Series) -> dict:
    """Classify the most recent observation of a daily returns series.

    `returns` must be daily (not annualized/resampled) simple returns,
    e.g. close.pct_change().dropna(), matching the input shape
    regime_analysis's own compute() expects.
    """
    if returns is None or len(returns) == 0:
        return {"status": "no_data", "regime": None}
    min_observations = _ROLLING_WINDOW + _VOL_BASELINE_WINDOW
    if len(returns) < min_observations:
        return {
            "status": "insufficient_data",
            "regime": None,
            "n_observations": len(returns),
        }

    vol = returns.rolling(_ROLLING_WINDOW).std() * _ANN_FACTOR_1D
    vol_baseline_mean = vol.rolling(_VOL_BASELINE_WINDOW).mean()
    vol_baseline_std = vol.rolling(_VOL_BASELINE_WINDOW).std().replace(0, pd.NA)
    vol_z = (vol - vol_baseline_mean) / vol_baseline_std

    latest_ret = float(returns.iloc[-1])
    latest_vol = float(vol.iloc[-1])
    latest_vol_z = vol_z.iloc[-1]
    if pd.isna(latest_vol) or pd.isna(latest_vol_z):
        return {
            "status": "insufficient_data",
            "regime": None,
            "n_observations": len(returns),
        }

    regime = _classify(latest_ret, float(latest_vol_z))
    return {
        "status": "ok",
        "regime": regime,
        "as_of_return": latest_ret,
        "as_of_vol": latest_vol,
        "vol_trailing_z": float(latest_vol_z),
        "n_observations": len(returns),
    }
