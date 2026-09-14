from __future__ import annotations

import numpy as np
import pandas as pd

# `vol_threshold = rolling_vol.quantile(vol_percentile)` used to be computed
# ONCE over the entire benchmark_returns series and then applied to every
# bar -- a look-ahead leak: bar 100's high_vol/not-high_vol label depended
# on volatility realized at bar 500, which hadn't happened yet in a
# backtest replaying bar-by-bar. This is the same defect
# vinu_initial_analysis/angles/regime_analysis/compute.py already fixed
# (per its own docstring) by comparing each bar's vol only against a
# trailing baseline computed from bars up to and including that bar.
# `_VOL_BASELINE_WINDOW`/`_VOL_Z_THRESHOLD` mirror compute.py's constants.
_VOL_BASELINE_WINDOW = 120
_VOL_Z_THRESHOLD = 1.0


def classify_regime(
    benchmark_returns: pd.Series,
    lookback: int = 21,
) -> pd.Series:
    rolling_vol = benchmark_returns.rolling(lookback, min_periods=2).std() * np.sqrt(252)
    rolling_vol = rolling_vol.bfill()
    vol_baseline_mean = rolling_vol.rolling(_VOL_BASELINE_WINDOW, min_periods=2).mean()
    vol_baseline_std = rolling_vol.rolling(_VOL_BASELINE_WINDOW, min_periods=2).std().replace(0, np.nan)
    vol_z = (rolling_vol - vol_baseline_mean) / vol_baseline_std

    regimes: list[str] = []
    for i in range(len(benchmark_returns)):
        ret = benchmark_returns.iloc[i]
        z = vol_z.iloc[i] if i >= lookback else vol_z.iloc[max(0, i - 1)]

        if pd.notna(z) and z > _VOL_Z_THRESHOLD:
            regimes.append("high_vol")
        elif ret > 0.01:
            regimes.append("bull")
        elif ret < -0.01:
            regimes.append("bear")
        else:
            regimes.append("sideways")

    return pd.Series(regimes, index=benchmark_returns.index)


def per_regime_performance(
    strategy_returns: pd.Series,
    regimes: pd.Series,
) -> dict[str, dict[str, float]]:
    df = pd.DataFrame({"return": strategy_returns, "regime": regimes}).dropna()
    result: dict[str, dict[str, float]] = {}
    for regime in df["regime"].unique():
        subset = df[df["regime"] == regime]["return"]
        if len(subset) < 2:
            continue
        total_ret = float(subset.sum())
        result[regime] = {
            "count": len(subset),
            "total_return": total_ret,
            "avg_return": float(subset.mean()),
            "std_return": float(subset.std()),
            "sharpe": float(subset.mean() / subset.std() * np.sqrt(252)) if subset.std() > 0 else 0.0,
            "win_rate": float((subset > 0).sum() / len(subset)),
        }
    return result
