from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from scipy import stats as _stats
from typing import Any


def _detect_gap_shocks(
    bars: pd.DataFrame,
    gap_std_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    close = bars["close"].astype(float)
    open_p = bars["open"].astype(float)
    gaps = (open_p - close.shift(1)) / close.shift(1)
    gap_mean = gaps.mean()
    gap_std = gaps.std()
    shocks = []
    for i in range(len(gaps)):
        if pd.isna(gaps.iloc[i]):
            continue
        z = (gaps.iloc[i] - gap_mean) / max(gap_std, 1e-12)
        if abs(z) > gap_std_threshold:
            shocks.append({
                "date": bars.index[i] if hasattr(bars.index, '__getitem__') else str(bars.index[i]),
                "type": "gap",
                "magnitude": float(gaps.iloc[i]),
                "z_score": float(z),
            })
    return shocks


def _detect_vol_shocks(
    bars: pd.DataFrame,
    vol_z_threshold: float = 2.0,
    window: int = 21,
) -> list[dict[str, Any]]:
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    daily_range = (high - low) / close
    rolling_mean = daily_range.rolling(window).mean()
    rolling_std = daily_range.rolling(window).std()
    shocks = []
    for i in range(len(daily_range)):
        if pd.isna(rolling_mean.iloc[i]) or pd.isna(rolling_std.iloc[i]):
            continue
        z = (daily_range.iloc[i] - rolling_mean.iloc[i]) / max(rolling_std.iloc[i], 1e-12)
        if z > vol_z_threshold:
            shocks.append({
                "date": bars.index[i] if hasattr(bars.index, '__getitem__') else str(bars.index[i]),
                "type": "vol_spike",
                "magnitude": float(z),
                "z_score": float(z),
            })
    return shocks


def _cross_reference_news(
    shocks: list[dict[str, Any]],
    news: list[dict] | None,
    news_window_days: int = 2,
) -> list[dict[str, Any]]:
    if not news:
        return shocks
    news_dates = set()
    for article in news:
        ts = article.get("published_at") or article.get("timestamp") or article.get("date", "")
        if ts:
            try:
                d = pd.Timestamp(ts).normalize()
                news_dates.add(d)
            except Exception:
                pass

    for shock in shocks:
        try:
            shock_date = pd.Timestamp(shock["date"]).normalize()
        except Exception:
            continue
        for nd in news_dates:
            if abs((shock_date - nd).days) <= news_window_days:
                shock["has_news"] = True
                shock["nearest_news_days"] = (shock_date - nd).days
                break
        else:
            shock["has_news"] = False
    return shocks


def _tag_shocks(
    bars: pd.DataFrame,
    news: list[dict] | None = None,
    gap_std_threshold: float = 2.0,
    vol_z_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    gap_shocks = _detect_gap_shocks(bars, gap_std_threshold)
    vol_shocks = _detect_vol_shocks(bars, vol_z_threshold)
    seen = set()
    combined = []
    for s in gap_shocks + vol_shocks:
        key = s["date"]
        if key not in seen:
            seen.add(key)
            combined.append(s)
    combined.sort(key=lambda x: x["date"])
    combined = _cross_reference_news(combined, news)
    return combined


def _compute_gap_fill_rate(
    bars: pd.DataFrame,
    shocks: list[dict[str, Any]],
    fill_window: int = 5,
) -> dict[str, Any]:
    close = bars["close"].astype(float)
    open_p = bars["open"].astype(float)
    gaps = (open_p - close.shift(1)) / close.shift(1)

    fill_ratios = []
    for shock in shocks:
        if shock["type"] != "gap":
            continue
        try:
            idx = bars.index.get_loc(pd.Timestamp(shock["date"]))
        except Exception:
            continue
        if idx + fill_window >= len(close):
            continue
        gap_size = abs(shock["magnitude"])
        if gap_size <= 0:
            continue
        entry = open_p.iloc[idx]
        future_close = close.iloc[idx + fill_window]
        if shock["magnitude"] > 0:
            filled = (entry - future_close) / entry
        else:
            filled = (future_close - entry) / entry
        fill_ratio = max(0.0, min(1.0, filled / gap_size))
        fill_ratios.append(fill_ratio)

    n = len(fill_ratios)
    if n < 2:
        return {
            "mean": float(np.mean(fill_ratios)) if fill_ratios else None,
            "n_observations": n,
            "confidence_interval": None,
            "status": "insufficient_sample" if n < 2 else "ok",
        }

    mean = float(np.mean(fill_ratios))
    se = float(np.std(fill_ratios, ddof=1) / np.sqrt(n))
    ci = _stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    return {
        "mean": mean,
        "n_observations": n,
        "confidence_interval": [float(ci[0]), float(ci[1])],
        "status": "ok",
    }


def _compute_vol_persistence(
    symbol: str,
    bars: pd.DataFrame,
) -> dict[str, Any]:
    from vinu_tools.compute.risk.volatility import garch_volatility

    close = bars["close"].astype(float)
    returns = close.pct_change().dropna().values
    if len(returns) < 20:
        return {"alpha": None, "beta": None, "persistence": None, "status": "insufficient_data"}

    _, alpha, beta, omega = garch_volatility(returns, fit=True, time_format="1D")
    persistence = alpha + beta
    return {
        "alpha": float(alpha),
        "beta": float(beta),
        "omega": float(omega),
        "persistence": float(persistence),
        "status": "ok",
    }


def _compute_drift_persistence(
    bars: pd.DataFrame,
    shocks: list[dict[str, Any]],
    max_lag: int = 20,
) -> dict[str, Any]:
    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()

    drift_lengths = []
    for shock in shocks:
        try:
            idx = bars.index.get_loc(pd.Timestamp(shock["date"]))
        except Exception:
            continue
        post_shock = returns.iloc[idx: idx + max_lag]
        if len(post_shock) < 3:
            continue
        autocorrs = [post_shock.autocorr(lag=l) for l in range(1, min(10, len(post_shock)))]
        autocorrs = [a for a in autocorrs if not pd.isna(a)]
        if not autocorrs:
            continue
        sign_streak = 0
        shock_sign = np.sign(shock["magnitude"])
        for r in post_shock.values:
            if np.sign(r) == shock_sign:
                sign_streak += 1
            else:
                break
        drift_lengths.append(sign_streak)

    n = len(drift_lengths)
    if n < 2:
        return {
            "mean_days": float(np.mean(drift_lengths)) if drift_lengths else None,
            "n_observations": n,
            "confidence_interval": None,
            "status": "insufficient_sample" if n < 2 else "ok",
        }

    mean = float(np.mean(drift_lengths))
    se = float(np.std(drift_lengths, ddof=1) / np.sqrt(n))
    ci = _stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    return {
        "mean_days": mean,
        "n_observations": n,
        "confidence_interval": [float(ci[0]), float(ci[1])],
        "status": "ok",
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
            "angle": "shock_personality",
            "status": "no_data",
        }])

    analysis_at = datetime.now(timezone.utc).isoformat()

    shocks = _tag_shocks(bars, news)
    gap_fill = _compute_gap_fill_rate(bars, shocks)
    vol_pers = _compute_vol_persistence(symbol, bars)
    drift = _compute_drift_persistence(bars, shocks)

    result = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "shock_personality",
        "status": "ok",
        "n_shocks": len(shocks),
        "gap_fill_rate": gap_fill,
        "vol_persistence": vol_pers,
        "drift_persistence_days": drift,
    }

    return pd.DataFrame([result])
