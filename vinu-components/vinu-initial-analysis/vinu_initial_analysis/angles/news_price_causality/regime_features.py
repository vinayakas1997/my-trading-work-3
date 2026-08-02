"""Point-in-time regime & volatility features for the significance classifier.

LEAK-SAFETY: the stored `regime_analysis` angle's `classify_regime` buckets
volatility against `vol.quantile(0.7)` computed over the ENTIRE sample series.
That threshold is a full-history constant, so if a news article itself caused
the high-vol spike that pushed the bar above the global 70th percentile, the
stored label would already embed the *post*-event move -- the exact thing
`ar_significant` measures. Feeding that label into the classifier would be a
fresh `impact_label`-style leak.

Every feature here is computed from bars STRICTLY UP TO the article's
timestamp: the event anchors to the last daily bar at/before `ts`, and the
21-day realized-vol is compared against a *trailing* baseline (the mean/std
of the same series up to that point), not a full-sample constant. These are
all knowable the instant the article publishes.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _completed_bar_index(daily_ts: np.ndarray, ts: int) -> int | None:
    """Last daily bar index with bar_ts <= ts, or None if none precedes it."""
    pos = int(np.searchsorted(daily_ts, ts, side="right")) - 1
    return pos if pos >= 0 else None


def _to_daily(close_by_ts: pd.Series) -> pd.DataFrame:
    """Collapse to one close per UTC calendar day (last bar in the day)."""
    idx = pd.to_datetime(close_by_ts.index.to_numpy(), unit="s", utc=True)
    tmp = pd.DataFrame({
        "bar_ts": close_by_ts.index.to_numpy(),
        "_day": idx.strftime("%Y-%m-%d"),
        "close": close_by_ts.to_numpy(),
    })
    daily = tmp.groupby("_day", as_index=False).agg({"bar_ts": "max", "close": "last"})
    return daily.sort_values("bar_ts").reset_index(drop=True)


def build_point_in_time_features(
    candles: list[dict[str, Any]],
    events: list[dict[str, Any]],
    vol_days: int = 21,
    rel_days: int = 20,
    vol_baseline_days: int = 120,
) -> dict[str, dict[str, Any]]:
    """Per-article-id pre-event regime/volatility features.

    Args:
        candles: symbol candles (any resolution, here 1min) ascending by bar_ts.
        events: impact rows, each with 'ts' and 'article_id'.

    Returns {article_id: {"regime_feature", "vol_21d", "ret_20d", "vol_trailing_z"}}.
    """
    if not candles or not events:
        return {}

    pdf = pd.DataFrame(candles).sort_values("bar_ts")
    if "bar_ts" not in pdf.columns or "close" not in pdf.columns or pdf.empty:
        return {}
    col_order = ["bar_ts", "close"]
    pdf = pdf[col_order].groupby("bar_ts", as_index=False).last()
    pdf["close"] = pdf["close"].ffill()
    pdf = pdf.dropna(subset=["close"])
    if pdf.empty:
        return {}

    daily = _to_daily(pdf.set_index("bar_ts")["close"])
    daily_ts = daily["bar_ts"].to_numpy(dtype=np.int64)
    daily_ret = daily["close"].pct_change()

    vol = daily_ret.rolling(vol_days).std() * np.sqrt(252)
    rel = daily["close"].pct_change(rel_days)

    vol_base_mean = vol.rolling(vol_baseline_days).mean()
    vol_base_std = vol.rolling(vol_baseline_days).std().replace(0, np.nan)
    vol_z = (vol - vol_base_mean) / vol_base_std

    result: dict[str, dict[str, Any]] = {}
    for ev in events:
        aid = ev.get("article_id")
        ts = int(ev.get("ts") or 0)
        if not aid or ts <= 0:
            continue
        idx = _completed_bar_index(daily_ts, ts)
        if idx is None or idx < 1:
            continue
        v = float(vol.iloc[idx]) if pd.notna(vol.iloc[idx]) else None
        r = float(rel.iloc[idx]) if pd.notna(rel.iloc[idx]) else None
        z = float(vol_z.iloc[idx]) if pd.notna(vol_z.iloc[idx]) else None

        rg: str | None = None
        if z is not None and z > 1.0:
            rg = "high_vol"
        elif r is not None:
            rg = "bull" if r > 0.01 else ("bear" if r < -0.01 else "sideways")

        result[aid] = {
            "regime_feature": rg,
            "vol_21d": v,
            "ret_20d": r,
            "vol_trailing_z": z,
        }
    return result