"""Regime Analysis — 4-regime classifier (bull/bear/high_vol/sideways).

Per 04-enhancement-of-each-angle/23-regime_analysis.md: the original
`vol.quantile(0.7)` threshold was a confirmed, cross-referenced look-ahead
leak (computed over the ENTIRE sample series, so an early bar's regime
label could depend on volatility that hadn't happened yet) --
`news_price_causality/regime_features.py`'s own docstring names this
defect directly and routes around it rather than fixing it here; this
module now adopts that same already-validated, point-in-time-safe
formula (rolling z-score against a 120-period trailing baseline) instead
of maintaining two divergent regime definitions in the same codebase.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import ann_factor
from vinu_initial_analysis.angles.signal_contract import tag_row

VOL_WINDOW = 21
VOL_BASELINE_WINDOW = 120
RETURN_WINDOW = 20
BULL_BEAR_THRESHOLD = 0.01
HIGH_VOL_Z_THRESHOLD = 1.0
# Real, derived floor for the corrected method (120-day trailing baseline
# + 21-day vol window), not the arbitrary N=100 convention used for the
# candle-count forecasters -- per the design doc SS3.
MIN_OBSERVATIONS = VOL_BASELINE_WINDOW + VOL_WINDOW


def classify_regime(ret_20d: float, vol_z: float) -> str:
    if pd.notna(vol_z) and vol_z > HIGH_VOL_Z_THRESHOLD:
        return "high_vol"
    if pd.notna(ret_20d) and ret_20d > BULL_BEAR_THRESHOLD:
        return "bull"
    if pd.notna(ret_20d) and ret_20d < -BULL_BEAR_THRESHOLD:
        return "bear"
    return "sideways"


def _compute_regime_frame(bars: pd.DataFrame, time_format: str | None) -> pd.DataFrame:
    """Point-in-time-safe regime frame: every row's `vol_trailing_z` (and
    therefore its `regime`) depends only on bars up to and including that
    row, never future data -- the fix for the leak described in this
    module's docstring. Columns: bar_ts, ret (single-period, for the
    regime_stats aggregation below -- unchanged from the original code),
    ret_20d/vol/vol_trailing_z (classification inputs), regime.
    """
    close = bars["close"].astype(float).reset_index(drop=True)
    af = ann_factor(time_format)

    single_period_ret = close.pct_change()
    ret_20d = close.pct_change(RETURN_WINDOW)
    vol = single_period_ret.rolling(VOL_WINDOW).std() * af
    vol_base_mean = vol.rolling(VOL_BASELINE_WINDOW).mean()
    vol_base_std = vol.rolling(VOL_BASELINE_WINDOW).std().replace(0, np.nan)
    vol_z = (vol - vol_base_mean) / vol_base_std

    bar_ts = bars["bar_ts"].reset_index(drop=True) if "bar_ts" in bars.columns else pd.Series(range(len(bars)))

    frame = pd.DataFrame({
        "bar_ts": bar_ts,
        "ret": single_period_ret,
        "ret_20d": ret_20d,
        "vol": vol,
        "vol_trailing_z": vol_z,
    }).dropna(subset=["ret", "ret_20d", "vol", "vol_trailing_z"])
    frame["regime"] = [
        classify_regime(r, z) for r, z in zip(frame["ret_20d"], frame["vol_trailing_z"])
    ]
    return frame.reset_index(drop=True)


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

    analysis_at = datetime.now(timezone.utc).isoformat()

    if len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "regime_analysis",
            "status": "insufficient_data",
            "n_observations": len(bars),
        }])

    rf = _compute_regime_frame(bars, time_format)
    if rf.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "regime_analysis",
            "status": "insufficient_data",
            "n_observations": len(bars),
        }])

    af = ann_factor(time_format)
    for rg, grp in rf.groupby("regime"):
        sr = (grp["ret"].mean() / grp["ret"].std() * af) if grp["ret"].std() > 0 else 0.0
        row = {
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
        }
        tag_row(row, "regime_feature")
        rows.append(row)

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

    transition_matrix: dict[tuple[str, str], int] = {}
    from_counts: dict[str, int] = {}
    for i in range(len(rf) - 1):
        pair = (rf["regime"].iloc[i], rf["regime"].iloc[i + 1])
        transition_matrix[pair] = transition_matrix.get(pair, 0) + 1
        from_counts[pair[0]] = from_counts.get(pair[0], 0) + 1

    for (from_r, to_r), cnt in sorted(transition_matrix.items()):
        n_from = from_counts[from_r]
        rows.append({
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": "regime_analysis",
            "metric": "transition",
            "regime_from": from_r,
            "regime_to": to_r,
            "count": cnt,
            # Normalized probability, always paired with its own sample
            # size (n_from_regime) -- per the design doc SS3, raw counts
            # alone force every consumer to independently figure out the
            # right denominator, matching this project's project-wide
            # "never present a rate without n" discipline.
            "n_from_regime": n_from,
            "transition_prob": round(cnt / n_from, 6) if n_from else 0.0,
        })

    return pd.DataFrame(rows)
