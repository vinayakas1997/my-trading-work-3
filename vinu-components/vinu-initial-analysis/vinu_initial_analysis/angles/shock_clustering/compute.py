"""Shock Clustering — shock-date detection plus shock-conditional
co-movement with watchlist peers.

Per 04-enhancement-of-each-angle/24-shock_clustering.md, two confirmed
bugs fixed here, not just flagged:

Bug #1 (leak, same class as regime_analysis's fix): the gap-based shock
trigger used `gaps.mean()`/`gaps.std()` over the ENTIRE bars series -- a
full-history constant -- right next to the intraday-range trigger, which
already correctly used a rolling window. Now both triggers use the same
rolling-window treatment.

Bug #2 (the angle didn't measure what its name/spec promised): the old
code reported `dynamic_covariance`'s unconditional trailing-63-day
correlation, with no awareness of which days were shocks at all --
`shock_dates` was computed but only ever used for reporting, never to
condition the correlation. Replaced entirely with genuinely
shock-conditional metrics: co-shock rate (did the peer also shock near
the anchor's shock date) and shock-day correlation (Pearson + bootstrap
CI, computed only on the anchor's shock-date subset, reusing the same
technique news_price_causality/peer_relative_strength already use). The
old generic correlation is dropped, not kept alongside -- it duplicated
peer_relative_strength (angle 21) with a strictly weaker method.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._helpers import pearson_with_ci
from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "shock_clustering"

GAP_ROLLING_WINDOW = 21
VOL_ROLLING_WINDOW = 21
SHOCK_Z_THRESHOLD = 2.0
# Real, derived floor for the rolling shock-detection windows to
# stabilize -- per the design doc SS3. Overridable via
# VINU_SHOCK_CLUSTERING_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)
# Below this many detected shock dates, co-shock-rate/correlation aren't
# reported at all (status: insufficient_shock_sample) -- same "don't
# report a rate built on almost nothing" discipline as
# pnl_attribution/news_price_causality.
MIN_SHOCK_DATES = 5
CO_SHOCK_WINDOW_DAYS = 1


def _detect_shocks(
    bars: pd.DataFrame,
    gap_std_threshold: float = SHOCK_Z_THRESHOLD,
    vol_z_threshold: float = SHOCK_Z_THRESHOLD,
) -> list[dict[str, Any]]:
    """Returns one dict per detected shock bar: bar_ts, date, trigger
    ("gap" or "range"), and the triggering z-score. Both triggers use a
    rolling window (the gap trigger no longer uses a full-sample
    constant -- see module docstring, Bug #1).
    """
    close = bars["close"].astype(float)
    open_p = bars["open"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)

    gaps = (open_p - close.shift(1)) / close.shift(1)
    gap_mean = gaps.rolling(GAP_ROLLING_WINDOW).mean()
    gap_std = gaps.rolling(GAP_ROLLING_WINDOW).std()

    daily_range = (high - low) / close
    vol_mean = daily_range.rolling(VOL_ROLLING_WINDOW).mean()
    vol_std = daily_range.rolling(VOL_ROLLING_WINDOW).std()

    shocks: list[dict[str, Any]] = []
    for i in range(len(bars)):
        ts = int(bars["bar_ts"].iloc[i])
        gz = gap_std.iloc[i]
        if pd.notna(gaps.iloc[i]) and pd.notna(gz) and gz > 0:
            gap_z = (gaps.iloc[i] - gap_mean.iloc[i]) / gz
            if abs(gap_z) > gap_std_threshold:
                shocks.append({
                    "bar_ts": ts, "date": str(pd.Timestamp(ts, unit="s").normalize().date()),
                    "trigger": "gap", "z": float(gap_z),
                })
                continue
        vz = vol_std.iloc[i]
        if pd.notna(vz) and vz > 0:
            vol_z = (daily_range.iloc[i] - vol_mean.iloc[i]) / vz
            if vol_z > vol_z_threshold:
                shocks.append({
                    "bar_ts": ts, "date": str(pd.Timestamp(ts, unit="s").normalize().date()),
                    "trigger": "range", "z": float(vol_z),
                })
    return shocks


def _detect_shock_dates(bars: pd.DataFrame, **kwargs: Any) -> list[str]:
    """Date-only view of `_detect_shocks`, kept for callers that only
    need the date list (e.g. the co-shock matcher below)."""
    return [s["date"] for s in _detect_shocks(bars, **kwargs)]


def _co_shock_and_correlation(
    anchor_shock_dates: list[str],
    anchor_returns_by_date: dict[str, float],
    peer_shock_dates: list[str],
    peer_returns_by_date: dict[str, float],
) -> dict[str, Any]:
    """For one peer: co-shock rate (peer also shocked within
    CO_SHOCK_WINDOW_DAYS of an anchor shock date) and Pearson correlation
    + bootstrapped CI of returns, restricted to the anchor's shock-date
    subset (only dates where both anchor and peer have a return).
    """
    anchor_dates_ts = pd.to_datetime(anchor_shock_dates)
    peer_dates_ts = pd.to_datetime(peer_shock_dates) if peer_shock_dates else pd.DatetimeIndex([])

    n_co_shocked = 0
    for d in anchor_dates_ts:
        if peer_dates_ts.empty:
            continue
        if (abs((peer_dates_ts - d).days) <= CO_SHOCK_WINDOW_DAYS).any():
            n_co_shocked += 1

    paired = [
        (anchor_returns_by_date[d], peer_returns_by_date[d])
        for d in anchor_shock_dates
        if d in anchor_returns_by_date and d in peer_returns_by_date
    ]
    result: dict[str, Any] = {
        "n_anchor_shock_dates": len(anchor_shock_dates),
        "n_co_shocked": n_co_shocked,
        "co_shock_rate": round(n_co_shocked / len(anchor_shock_dates), 4) if anchor_shock_dates else 0.0,
        "n_shock_day_pairs": len(paired),
    }
    if len(paired) >= 5:
        anchor_vals = np.array([p[0] for p in paired])
        peer_vals = np.array([p[1] for p in paired])
        ci = pearson_with_ci(anchor_vals, peer_vals)
        result["shock_day_correlation"] = ci["corr"]
        result["correlation_ci"] = [ci["ci_lower"], ci["ci_upper"]]
    else:
        result["shock_day_correlation"] = None
        result["correlation_ci"] = None
    return result


def _returns_by_date(bars: pd.DataFrame) -> dict[str, float]:
    close = bars["close"].astype(float)
    ret = close.pct_change()
    out: dict[str, float] = {}
    for i in range(len(bars)):
        if pd.isna(ret.iloc[i]):
            continue
        ts = int(bars["bar_ts"].iloc[i])
        out[str(pd.Timestamp(ts, unit="s").normalize().date())] = float(ret.iloc[i])
    return out


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
    price_client: Any = None,
) -> pd.DataFrame:
    if bars is None or bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": datetime.now(timezone.utc).isoformat(),
            "angle": "shock_clustering",
            "status": "no_data",
        }])

    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "shock_clustering",
            "status": "insufficient_data",
            "n_observations": len(bars),
        }])

    shocks = _detect_shocks(bars)
    shock_dates = [s["date"] for s in shocks]

    if len(shock_dates) < MIN_SHOCK_DATES:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "shock_clustering",
            "status": "insufficient_shock_sample",
            "n_shock_dates": len(shock_dates),
        }])

    anchor_returns = _returns_by_date(bars)

    # Peer universe (watchlist), each fetched with full OHLC so their own
    # shocks can be independently detected -- not just close prices.
    peer_bars: dict[str, pd.DataFrame] = {}
    try:
        if price_client is not None:
            watch = price_client.get_watchlist() or []
            for sym in sorted(set(watch) - {symbol}):
                candles = price_client.get_candles(sym, from_ts=from_ts, to_ts=to_ts, interval="1D", limit=50000)
                if candles and len(candles) >= MIN_OBSERVATIONS:
                    peer_bars[sym] = pd.DataFrame(candles).sort_values("bar_ts").reset_index(drop=True)
    except Exception:
        pass

    cluster_members: list[dict[str, Any]] = []
    for peer_sym, p_bars in peer_bars.items():
        peer_shock_dates = _detect_shock_dates(p_bars)
        peer_returns = _returns_by_date(p_bars)
        stats = _co_shock_and_correlation(shock_dates, anchor_returns, peer_shock_dates, peer_returns)
        cluster_members.append({"symbol": peer_sym, **stats})

    cluster_members.sort(key=lambda m: -(m["co_shock_rate"] or 0.0))

    result = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": "shock_clustering",
        "status": "ok",
        "n_shock_dates": len(shock_dates),
        "shock_dates": shock_dates[:10],
        "cluster_members": cluster_members,
    }
    return pd.DataFrame([result])
