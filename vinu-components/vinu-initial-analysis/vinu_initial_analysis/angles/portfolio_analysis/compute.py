"""Portfolio Analysis — rolling beta, beta-hedged Sharpe for single symbol"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone


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
            "time_format": time_format,
            "angle": "portfolio_analysis",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns) < 10:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "portfolio_analysis",
            "status": "insufficient_data",
            "n_observations": len(returns),
        }])

    rets = returns.values
    n = len(rets)
    ann_factor = np.sqrt(252)

    raw_sharpe = float(rets.mean() / rets.std() * ann_factor) if rets.std() > 0 else 0.0
    ann_vol = float(rets.std() * ann_factor)
    ann_ret = float(rets.mean() * 252)

    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "time_format": time_format,
        "angle": "portfolio_analysis",
        "metric": "summary",
        "ann_return": round(ann_ret, 6),
        "ann_vol": round(ann_vol, 6),
        "sharpe": round(raw_sharpe, 4),
        "n_observations": n,
    })

    for window in [21, 63, 126]:
        roll_ret = returns.rolling(window).mean() * 252
        roll_vol = returns.rolling(window).std() * ann_factor
        roll_sr = roll_ret / roll_vol
        row = {
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "portfolio_analysis",
            "metric": f"rolling_{window}d",
            "rolling_return_mean": float(roll_ret.mean()),
            "rolling_return_std": float(roll_ret.std()),
            "rolling_vol_mean": float(roll_vol.mean()),
            "rolling_vol_std": float(roll_vol.std()),
            "rolling_sharpe_mean": float(roll_sr.mean()),
            "rolling_sharpe_std": float(roll_sr.std()),
            "rolling_sharpe_pos_pct": float((roll_sr > 0).mean()),
        }
        rows.append(row)

    smoothed = returns.rolling(21).mean().dropna()
    common = pd.DataFrame({"raw": returns, "smooth": smoothed}).dropna()

    if len(common) > 10:
        raw = common["raw"].values
        smooth = common["smooth"].values
        beta = float(np.cov(raw, smooth)[0, 1] / np.var(smooth)) if np.var(smooth) > 0 else 0.0
        hedged = raw - beta * smooth
        hedged_sharpe = float(hedged.mean() / hedged.std() * ann_factor) if hedged.std() > 0 else 0.0

        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "portfolio_analysis",
            "metric": "beta_hedged",
            "beta_to_smooth": round(beta, 4),
            "raw_sharpe": round(raw_sharpe, 4),
            "hedged_sharpe": round(hedged_sharpe, 4),
            "hedged_return": round(float(hedged.mean() * 252), 6),
            "hedged_vol": round(float(hedged.std() * ann_factor), 6),
            "n_observations": len(common),
        })

    if len(common) > 60:
        roll_beta = common["raw"].rolling(60).cov(common["smooth"]) / common["smooth"].rolling(60).var()
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "time_format": time_format,
            "angle": "portfolio_analysis",
            "metric": "rolling_beta_60d",
            "rolling_beta_mean": float(roll_beta.mean()),
            "rolling_beta_std": float(roll_beta.std()),
            "rolling_beta_min": float(roll_beta.min()),
            "rolling_beta_max": float(roll_beta.max()),
        })

    return pd.DataFrame(rows)
