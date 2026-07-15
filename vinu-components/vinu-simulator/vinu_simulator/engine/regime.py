from __future__ import annotations

import numpy as np
import pandas as pd


def classify_regime(
    benchmark_returns: pd.Series,
    lookback: int = 21,
    vol_percentile: float = 0.7,
) -> pd.Series:
    rolling_vol = benchmark_returns.rolling(lookback, min_periods=2).std() * np.sqrt(252)
    rolling_vol = rolling_vol.bfill()
    vol_threshold = rolling_vol.quantile(vol_percentile)

    regimes: list[str] = []
    for i in range(len(benchmark_returns)):
        ret = benchmark_returns.iloc[i]
        vol = rolling_vol.iloc[i] if i >= lookback else rolling_vol.iloc[max(0, i - 1)]

        if vol > vol_threshold:
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
