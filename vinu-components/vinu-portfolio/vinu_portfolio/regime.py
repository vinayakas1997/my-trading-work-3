from __future__ import annotations

import pandas as pd

# Mirrors vinu_initial_analysis/angles/regime_analysis/compute.py's own
# classify_regime() thresholding exactly (21-day rolling vol, 0.7 quantile
# threshold, same 4 labels) -- reimplemented here rather than imported
# across the service boundary, and reimplemented rather than read from that
# angle's stored output because that output is a window-aggregate (per-regime
# win rate/Sharpe/pct_of_time across the whole analyzed history), not a
# single "today's regime" value. See daily-allocation/SKILL.md for the
# full explanation.
_ROLLING_WINDOW = 21
_VOL_QUANTILE = 0.7
_ANN_FACTOR_1D = 252 ** 0.5


def _classify(ret: float, vol: float, vol_thresh: float) -> str:
    if vol > vol_thresh:
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
    if len(returns) < _ROLLING_WINDOW:
        return {
            "status": "insufficient_data",
            "regime": None,
            "n_observations": len(returns),
        }

    vol = returns.rolling(_ROLLING_WINDOW).std() * _ANN_FACTOR_1D
    vol_thresh = vol.quantile(_VOL_QUANTILE)
    latest_ret = float(returns.iloc[-1])
    latest_vol = float(vol.iloc[-1])
    if pd.isna(latest_vol) or pd.isna(vol_thresh):
        return {
            "status": "insufficient_data",
            "regime": None,
            "n_observations": len(returns),
        }

    regime = _classify(latest_ret, latest_vol, float(vol_thresh))
    return {
        "status": "ok",
        "regime": regime,
        "as_of_return": latest_ret,
        "as_of_vol": latest_vol,
        "vol_threshold": float(vol_thresh),
        "n_observations": len(returns),
    }
