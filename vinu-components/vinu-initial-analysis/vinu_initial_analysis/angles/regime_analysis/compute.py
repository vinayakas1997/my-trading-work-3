"""Regime Analysis — 4-regime classifier (bull/bear/high_vol/sideways)"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import ann_factor


def classify_regime(ret: float, vol: float, vol_thresh: float) -> str:
    if vol > vol_thresh:
        return "high_vol"
    if ret > 0.01:
        return "bull"
    if ret < -0.01:
        return "bear"
    return "sideways"


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    rows = []
    if bars is None:
        bars = pd.DataFrame()
    if bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "angle": "regime_analysis",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns) < 21:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "regime_analysis",
            "status": "insufficient_data",
            "n_observations": len(returns),
        }])

    af = ann_factor(time_format)
    vol = returns.rolling(21).std() * af
    vol_thresh = vol.quantile(0.7)
    rf = pd.DataFrame({"ret": returns, "vol": vol}).dropna()
    rf["regime"] = rf.apply(lambda r: classify_regime(r["ret"], r["vol"], vol_thresh), axis=1)

    for rg, grp in rf.groupby("regime"):
        sr = (grp["ret"].mean() / grp["ret"].std() * af) if grp["ret"].std() > 0 else 0.0
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "regime_analysis",
            "metric": "regime_stats",
            "regime": rg,
            "count": len(grp),
            "total_return": float((1 + grp["ret"]).prod() - 1),
            "avg_return": float(grp["ret"].mean()),
            "std_return": float(grp["ret"].std()),
            "sharpe": round(sr, 4),
            "win_rate": float((grp["ret"] > 0).mean()),
            "pct_of_time": float(len(grp) / len(rf)),
        })

    transitions = (rf["regime"] != rf["regime"].shift(1)).sum()
    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "regime_analysis",
        "metric": "regime_transitions",
        "regime": "all",
        "count": int(transitions),
        "total_observations": len(rf),
    })

    transition_matrix = {}
    for i in range(len(rf) - 1):
        pair = (rf["regime"].iloc[i], rf["regime"].iloc[i + 1])
        transition_matrix[pair] = transition_matrix.get(pair, 0) + 1

    for (from_r, to_r), cnt in sorted(transition_matrix.items()):
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "regime_analysis",
            "metric": "transition",
            "regime_from": from_r,
            "regime_to": to_r,
            "count": cnt,
        })

    return pd.DataFrame(rows)
