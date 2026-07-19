"""Trend Session Structure — session-level analysis of trend_lifecycle extrema.

Reads trend_lifecycle's stored snapshots (Option A: single source of truth,
no duplicated peak detection) and reports which trading session produces
reliable tops: per-session counts, drawdown, recovery, and KNN similarity.

Intraday only — on 1D+ bars every peak lands in one session bucket and a
breakdown would be an artifact, so those formats return not_applicable.

Runs after trend_lifecycle within a run (alphabetical discovery order), so it
sees the current run's freshly written snapshots.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from vinu_initial_analysis.config import load_config
from vinu_initial_analysis.storage.parquet import AngleStorage
from .sessions import dedup_latest_snapshots, aggregate_sessions, build_summary

LOG = logging.getLogger(__name__)

_UPSTREAM_ANGLE = "trend_lifecycle"
_INTRADAY_FORMATS = {"15min", "1H", "4H"}


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    angle_name = "trend_session_structure"
    tf = time_format or "1H"

    def _summary_only(status: str) -> pd.DataFrame:
        return pd.DataFrame([{
            "analysis_at": now, "angle": angle_name, "type": "summary",
            "status": status, "total_peaks": 0, "total_troughs": 0,
            "n_sessions_with_data": 0, "n_qualifying_sessions": 0,
            "best_session": None, "worst_session": None,
        }])

    if tf not in _INTRADAY_FORMATS:
        return _summary_only("not_applicable")

    try:
        config = load_config()
        storage = AngleStorage(config.data_root)
        upstream = storage.read(symbol, _UPSTREAM_ANGLE)
    except Exception:
        LOG.warning("Could not read %s data for %s", _UPSTREAM_ANGLE, symbol)
        upstream = pd.DataFrame()

    if upstream.empty or "type" not in upstream.columns:
        return _summary_only("no_upstream_data")

    if "time_format" in upstream.columns:
        upstream = upstream[upstream["time_format"] == tf]
    if upstream.empty:
        return _summary_only("no_upstream_data")

    snapshots = dedup_latest_snapshots(upstream)
    if snapshots.empty:
        return _summary_only("no_upstream_data")

    matches = upstream[upstream["type"] == "match"]

    session_rows = aggregate_sessions(snapshots, matches)
    summary = build_summary(session_rows)

    rows = []
    for row in session_rows:
        row["analysis_at"] = now
        row["angle"] = angle_name
        rows.append(row)
    summary["analysis_at"] = now
    summary["angle"] = angle_name
    rows.append(summary)

    return pd.DataFrame(rows)
