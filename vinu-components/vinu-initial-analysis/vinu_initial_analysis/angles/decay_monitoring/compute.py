"""Decay Monitoring — rolling IC, IR, health score, decay curve for 4 real factor signals."""

import pandas as pd
import numpy as np
from datetime import datetime, timezone


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, np.nan)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _build_factor_signals(close: pd.Series) -> dict[str, pd.Series]:
    returns = close.pct_change()
    lag1_ret = returns.shift(1)
    sma_10 = close.rolling(10).mean()
    sma_30 = close.rolling(30).mean()
    sma_cross = (sma_10 > sma_30).astype(float)
    rsi = _compute_rsi(close, 14)
    rsi_signal = ((rsi < 30).astype(float) - (rsi > 70).astype(float))
    vol = returns.rolling(20).std()
    vol_factor = -vol
    return {
        "lag1_ret": lag1_ret,
        "sma_cross": sma_cross,
        "rsi_signal": rsi_signal,
        "vol_factor": vol_factor,
    }


def _compute_ic_series(factor: pd.Series, fwd_ret: pd.Series, window: int = 60) -> pd.Series:
    combined = pd.DataFrame({"f": factor, "r": fwd_ret}).dropna()
    if len(combined) < window:
        return pd.Series(dtype=float)
    return combined["f"].rolling(window).corr(combined["r"])


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
            "angle": "decay_monitoring",
            "status": "no_data",
        }])

    close = bars["close"].astype(float)
    returns = close.pct_change()
    fwd_ret = returns.shift(-1)
    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(returns.dropna()) < 30:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "decay_monitoring",
            "status": "insufficient_data",
            "n_observations": len(returns.dropna()),
        }])

    signals = _build_factor_signals(close)
    decay_windows = [10, 20, 40, 60, 120]

    for signal_name, factor in signals.items():
        ic_series = _compute_ic_series(factor, fwd_ret, window=60)
        if ic_series.empty:
            continue

        ic_mean = float(ic_series.mean())
        ic_std = float(ic_series.std())
        ic_pos_pct = float((ic_series > 0).mean())
        ic_sharpe = ic_mean / ic_std if ic_std > 0 else 0.0

        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "decay_monitoring",
            "signal": signal_name,
            "metric": "ic_computation",
            "ic_mean": round(ic_mean, 4),
            "ic_std": round(ic_std, 4),
            "ic_pos_pct": round(ic_pos_pct, 4),
            "ic_sharpe": round(ic_sharpe, 4),
            "n_observations": len(ic_series),
        })

        roll_ir = ic_series.rolling(20).mean() / ic_series.rolling(20).std().replace(0, np.nan)
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "decay_monitoring",
            "signal": signal_name,
            "metric": "rolling_information_ratio",
            "ir_mean": round(float(roll_ir.mean()), 4),
            "ir_std": round(float(roll_ir.std()), 4),
            "ir_pos_pct": round(float((roll_ir > 0).mean()), 4),
        })

        score = 0
        score += 2 if ic_mean > 0 else -2
        score += 1 if ic_std < 0.5 else -1
        score += 2 if ic_pos_pct > 0.5 else -2
        score += 1 if roll_ir.mean() > 0 else -1
        score += 1 if (roll_ir > 0).mean() > 0.5 else -1
        if score >= 3:
            status = "HEALTHY"
        elif score >= 0:
            status = "WARNING"
        elif score >= -5:
            status = "DECAYED"
        else:
            status = "CRITICAL"

        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "decay_monitoring",
            "signal": signal_name,
            "metric": "health_score",
            "health_score": score,
            "health_status": status,
        })

        for w in decay_windows:
            ic_w = _compute_ic_series(factor, fwd_ret, window=w)
            if ic_w.empty:
                continue
            rows.append({
                "symbol": symbol,
                "analysis_at": analysis_at,
                "angle": "decay_monitoring",
                "signal": signal_name,
                "metric": "decay_curve",
                "window": w,
                "ic_mean": round(float(ic_w.mean()), 4),
                "n_observations": len(ic_w),
            })

    returns_ic = returns.rolling(60).corr(returns.shift(1)).dropna()
    rows.append({
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "decay_monitoring",
        "signal": "all",
        "metric": "return_autocorrelation",
        "return_ic_mean": round(float(returns_ic.mean()), 4),
        "return_ic_std": round(float(returns_ic.std()), 4),
    })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
