"""Shock Personality — post-shock behavioral profile for a single symbol.

Per 04-enhancement-of-each-angle/25-shock_personality.md, three confirmed
bugs fixed here:

Bug #1 (leak, independently reimplemented duplicate of shock_clustering's
own fixed bug, not shared code): `_detect_gap_shocks`'s `gap_mean`/
`gap_std` were computed over the ENTIRE bars series -- a full-history
constant. Fixed to a rolling(21) window, matching the vol-spike trigger
right next to it (which was already correct). This matters beyond
backtest correctness: a full-sample statistic can't be computed live --
the rolling version is the same calculation whether run in a backtest or
in production every day.

Bug #2 (computed, then discarded): `_compute_drift_persistence` computed
per-shock post-event return autocorrelation but only ever checked
whether at least one value was non-NaN -- the actual numbers were thrown
away. Now aggregated and reported as `drift_mean_autocorr`, alongside
the existing sign-streak `drift_persistence_days`.

Bug #3 (computed, then discarded): `_cross_reference_news` tagged every
shock with `has_news`/`nearest_news_days`, but `compute()`'s output only
ever reported an aggregate `n_shocks` count -- the per-shock news
information never reached storage. Now surfaced via backtest.py's new
per-shock rows, and used here to split gap_fill_rate/drift metrics by
news presence.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timezone
from typing import Any

from vinu_initial_analysis.angles._helpers import mean_with_ci
from vinu_initial_analysis.config import get_angle_setting

ANGLE_NAME = "shock_personality"

GAP_ROLLING_WINDOW = 21
VOL_ROLLING_WINDOW = 21
# Real floor: the rolling windows' own requirement, not the arbitrary
# N=100 convention -- per the design doc SS3, this angle's actual
# gating constraint is how many shocks get detected, not raw candle count.
# Overridable via VINU_SHOCK_PERSONALITY_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", 21)


def _detect_gap_shocks(
    bars: pd.DataFrame,
    gap_std_threshold: float = 2.0,
) -> list[dict[str, Any]]:
    close = bars["close"].astype(float)
    open_p = bars["open"].astype(float)
    gaps = (open_p - close.shift(1)) / close.shift(1)
    gap_mean = gaps.rolling(GAP_ROLLING_WINDOW).mean()
    gap_std = gaps.rolling(GAP_ROLLING_WINDOW).std()
    shocks = []
    for i in range(len(gaps)):
        if pd.isna(gaps.iloc[i]) or pd.isna(gap_std.iloc[i]):
            continue
        z = (gaps.iloc[i] - gap_mean.iloc[i]) / max(gap_std.iloc[i], 1e-12)
        if abs(z) > gap_std_threshold:
            shocks.append({
                "date": int(bars["bar_ts"].iloc[i]),
                "idx": i,
                "type": "gap",
                "magnitude": float(gaps.iloc[i]),
                "z_score": float(z),
            })
    return shocks


def _detect_vol_shocks(
    bars: pd.DataFrame,
    vol_z_threshold: float = 2.0,
    window: int = VOL_ROLLING_WINDOW,
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
                "date": int(bars["bar_ts"].iloc[i]),
                "idx": i,
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
        for shock in shocks:
            shock.setdefault("has_news", False)
            shock.setdefault("nearest_news_days", None)
        return shocks
    news_dates = set()
    for article in news:
        ts = article.get("sort_ts") or article.get("published_at") or article.get("timestamp") or article.get("date")
        if ts is None or ts == "":
            continue
        try:
            if isinstance(ts, (int, float, np.integer, np.floating)):
                d = pd.Timestamp(int(ts), unit="s").normalize()
            else:
                d = pd.Timestamp(ts).normalize()
            news_dates.add(d)
        except Exception:
            pass

    for shock in shocks:
        try:
            shock_date = pd.Timestamp(int(shock["date"]), unit="s").normalize()
        except Exception:
            continue
        for nd in news_dates:
            if abs((shock_date - nd).days) <= news_window_days:
                shock["has_news"] = True
                shock["nearest_news_days"] = (shock_date - nd).days
                break
        else:
            shock["has_news"] = False
            shock["nearest_news_days"] = None
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

    fill_ratios = []
    for shock in shocks:
        if shock["type"] != "gap":
            continue
        idx = shock.get("idx")
        if idx is None or idx + fill_window >= len(close):
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

    return mean_with_ci(fill_ratios)


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


def _compute_drift_metrics(
    bars: pd.DataFrame,
    shocks: list[dict[str, Any]],
    max_lag: int = 20,
) -> dict[str, dict[str, Any]]:
    """Two complementary post-shock drift views: `drift_persistence_days`
    (existing sign-streak, truncates at the first reversal) and
    `drift_mean_autocorr` (new -- mean lag-1-through-9 return
    autocorrelation following each shock, previously computed then
    discarded, see module docstring Bug #2). Returns both under one call
    so shocks only need to be walked once.
    """
    close = bars["close"].astype(float)
    returns = close.pct_change().dropna()

    drift_lengths = []
    mean_autocorrs = []
    for shock in shocks:
        idx = shock.get("idx")
        if idx is None:
            continue
        post_shock = returns.iloc[idx: idx + max_lag]
        if len(post_shock) < 3:
            continue
        autocorrs = [post_shock.autocorr(lag=l) for l in range(1, min(10, len(post_shock)))]
        autocorrs = [a for a in autocorrs if not pd.isna(a)]
        if not autocorrs:
            continue
        mean_autocorrs.append(float(np.mean(autocorrs)))

        sign_streak = 0
        shock_sign = np.sign(shock["magnitude"])
        for r in post_shock.values:
            if np.sign(r) == shock_sign:
                sign_streak += 1
            else:
                break
        drift_lengths.append(sign_streak)

    drift_persistence = mean_with_ci(drift_lengths)
    drift_persistence = {"mean_days": drift_persistence.pop("mean"), **drift_persistence}
    return {
        "drift_persistence_days": drift_persistence,
        "drift_mean_autocorr": mean_with_ci(mean_autocorrs),
    }


def _news_split(shocks: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    news_shocks = [s for s in shocks if s.get("has_news")]
    no_news_shocks = [s for s in shocks if not s.get("has_news")]
    return news_shocks, no_news_shocks


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

    if len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "shock_personality",
            "status": "insufficient_data",
            "n_observations": len(bars),
        }])

    shocks = _tag_shocks(bars, news)
    gap_fill = _compute_gap_fill_rate(bars, shocks)
    vol_pers = _compute_vol_persistence(symbol, bars)
    drift = _compute_drift_metrics(bars, shocks)

    news_shocks, no_news_shocks = _news_split(shocks)

    result = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "shock_personality",
        "status": "ok",
        "n_shocks": len(shocks),
        "n_shocks_with_news": len(news_shocks),
        "gap_fill_rate": gap_fill,
        "gap_fill_rate_news": _compute_gap_fill_rate(bars, news_shocks),
        "gap_fill_rate_no_news": _compute_gap_fill_rate(bars, no_news_shocks),
        "vol_persistence": vol_pers,
        "drift_persistence_days": drift["drift_persistence_days"],
        "drift_mean_autocorr": drift["drift_mean_autocorr"],
        "drift_persistence_days_news": _compute_drift_metrics(bars, news_shocks)["drift_persistence_days"],
        "drift_persistence_days_no_news": _compute_drift_metrics(bars, no_news_shocks)["drift_persistence_days"],
    }

    return pd.DataFrame([result])
