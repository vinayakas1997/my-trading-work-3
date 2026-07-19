"""Session-level aggregation of trend_lifecycle peak/trough snapshots.

Pure functions — no storage access, fully testable with hand-built DataFrames.

Statistical guards:
- Drawdown/recovery stats use MATURE outcomes only (outcome_mature == True).
- Rates and averages are suppressed (None) for sessions below _MIN_SAMPLE
  mature peaks, so small-sample noise never masquerades as signal. Counts
  are always reported.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

_MIN_SAMPLE = 10
_MIN_MATCHES_FOR_SIMILARITY = 5
_SESSIONS = ["premarket", "regular", "afterhours", "closed"]


def dedup_latest_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the latest stored row per (inflection_type, bar_ts).

    storage.read() concatenates ALL historical runs and trend_lifecycle
    recaptures immature snapshots on later runs, so the same extremum can
    appear multiple times. The row with the newest stored_at wins (it carries
    the finalized outcome). Falls back to input order when stored_at is absent.
    """
    if df.empty or "type" not in df.columns:
        return pd.DataFrame()
    snaps = df[df["type"] == "snapshot"].copy()
    if snaps.empty or "bar_ts" not in snaps.columns or "inflection_type" not in snaps.columns:
        return pd.DataFrame()
    if "stored_at" in snaps.columns:
        snaps = snaps.sort_values("stored_at", kind="stable")
    return snaps.drop_duplicates(subset=["inflection_type", "bar_ts"], keep="last")


def aggregate_sessions(snapshots: pd.DataFrame, matches: pd.DataFrame | None = None) -> list[dict]:
    """Group deduplicated snapshots by session and emit one stats row per session.

    matches (optional) are trend_lifecycle rows with type=="match"; their
    similarity is attributed to the session of the queried peak via query_bar_ts.
    """
    if snapshots.empty or "session" not in snapshots.columns:
        return []
    peaks = snapshots[snapshots["inflection_type"] == "peak"]
    troughs = snapshots[snapshots["inflection_type"] == "trough"]

    # Map peak bar_ts -> session so match rows can be attributed
    peak_session = {}
    for _, row in peaks.iterrows():
        if pd.notna(row.get("bar_ts")) and pd.notna(row.get("session")):
            peak_session[int(row["bar_ts"])] = row["session"]

    match_sims: dict[str, list[float]] = {s: [] for s in _SESSIONS}
    if matches is not None and not matches.empty and "query_bar_ts" in matches.columns:
        for _, m in matches.iterrows():
            q_ts = m.get("query_bar_ts")
            sim = m.get("similarity")
            if pd.isna(q_ts) or pd.isna(sim):
                continue
            session = peak_session.get(int(q_ts))
            if session in match_sims:
                match_sims[session].append(float(sim))

    rows = []
    for session in _SESSIONS:
        s_peaks = peaks[peaks["session"] == session]
        s_troughs = troughs[troughs["session"] == session] if not troughs.empty else troughs
        if s_peaks.empty and (s_troughs is None or s_troughs.empty):
            continue

        if "outcome_mature" in s_peaks.columns:
            mature = s_peaks[s_peaks["outcome_mature"] == True]  # noqa: E712
        else:
            mature = s_peaks.iloc[0:0]
        n_mature = len(mature)
        meets_floor = n_mature >= _MIN_SAMPLE

        row = {
            "type": "session_stats",
            "session": session,
            "n_peaks": len(s_peaks),
            "n_troughs": 0 if s_troughs is None else len(s_troughs),
            "n_mature_peaks": n_mature,
            "meets_floor": meets_floor,
            "min_sample_floor": _MIN_SAMPLE,
            "avg_drawdown_pct": None,
            "median_drawdown_pct": None,
            "worst_drawdown_pct": None,
            "recovery_rate": None,
            "avg_recovery_bars": None,
            "avg_runup_bars": None,
            "avg_volume_zscore": None,
            "avg_upper_wick_pct": None,
            "avg_similarity": None,
            "n_matches": len(match_sims[session]),
        }

        if meets_floor:
            dd = mature["drawdown_pct"].dropna() if "drawdown_pct" in mature.columns else pd.Series(dtype=float)
            if not dd.empty:
                row["avg_drawdown_pct"] = round(float(dd.mean()), 4)
                row["median_drawdown_pct"] = round(float(dd.median()), 4)
                row["worst_drawdown_pct"] = round(float(dd.min()), 4)
            if "recovery_time_bars" in mature.columns:
                recovered = mature["recovery_time_bars"].dropna()
                row["recovery_rate"] = round(len(recovered) / n_mature, 4)
                if not recovered.empty:
                    row["avg_recovery_bars"] = round(float(recovered.astype(float).mean()), 2)
            for src, dest in (
                ("runup_bars", "avg_runup_bars"),
                ("volume_zscore_20", "avg_volume_zscore"),
                ("upper_wick_pct", "avg_upper_wick_pct"),
            ):
                if src in mature.columns:
                    vals = mature[src].dropna()
                    if not vals.empty:
                        row[dest] = round(float(vals.astype(float).mean()), 4)

        if len(match_sims[session]) >= _MIN_MATCHES_FOR_SIMILARITY:
            row["avg_similarity"] = round(float(np.mean(match_sims[session])), 4)

        rows.append(row)
    return rows


def build_summary(session_rows: list[dict]) -> dict:
    """Cross-session summary. best/worst ranked only among floor-meeting sessions."""
    qualifying = [
        r for r in session_rows
        if r.get("meets_floor") and r.get("avg_drawdown_pct") is not None
    ]
    best = worst = None
    if qualifying:
        # drawdowns are negative: "best" session = shallowest avg drawdown
        ranked = sorted(qualifying, key=lambda r: r["avg_drawdown_pct"], reverse=True)
        best = ranked[0]["session"]
        worst = ranked[-1]["session"]
    return {
        "type": "summary",
        "status": "completed" if session_rows else "no_sessions",
        "total_peaks": sum(r["n_peaks"] for r in session_rows),
        "total_troughs": sum(r["n_troughs"] for r in session_rows),
        "n_sessions_with_data": len(session_rows),
        "n_qualifying_sessions": len(qualifying),
        "min_sample_floor": _MIN_SAMPLE,
        "best_session": best,
        "worst_session": worst,
    }
