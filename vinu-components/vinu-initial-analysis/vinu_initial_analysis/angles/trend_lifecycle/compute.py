"""Trend Lifecycle -- peak/trough pattern library, KNN matching, lifecycle stage, trade signals.

Orchestration entry point. Discovers new peaks, captures snapshots,
matches against historical library, classifies stage, and generates signals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from vinu_initial_analysis.config import load_config
from vinu_initial_analysis.storage.parquet import AngleStorage
from .peaks import detect_peaks, detect_troughs, merge_inflections, filter_alternating_inflections
from .snapshots import capture_all_peaks, capture_all_troughs, compute_indicators
from .patterns import load_pattern_library, build_feature_matrix, find_similar, get_library_stats
from .lifecycle import classify
from .signals import generate_signals

LOG = logging.getLogger(__name__)

_MIN_PEAK_DROP_PCT = {
    "15min": -2.0,
    "1H": -3.0,
    "4H": -4.0,
    "1D": -5.0,
    "1W": -5.0,
}


def _mature_snapshot_ts(df: pd.DataFrame, inflection: str, tf: str) -> set:
    """bar_ts of stored snapshots whose outcome is final (outcome_mature=True).

    Legacy rows without the flag are treated as immature so in-window
    extrema get recaptured with corrected outcomes.
    """
    if df.empty or "type" not in df.columns or "inflection_type" not in df.columns:
        return set()
    snaps = df[(df["type"] == "snapshot") & (df["inflection_type"] == inflection)]
    if snaps.empty or "bar_ts" not in snaps.columns:
        return set()
    if "time_format" in snaps.columns:
        snaps = snaps[(snaps["time_format"].isna()) | (snaps["time_format"] == tf)]
    if "outcome_mature" not in snaps.columns:
        return set()
    snaps = snaps[snaps["outcome_mature"] == True]  # noqa: E712
    return set(snaps["bar_ts"].unique())


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    angle_name = "trend_lifecycle"
    rows = []

    if bars is None or bars.empty:
        return pd.DataFrame([{
            "analysis_at": now, "angle": angle_name, "type": "summary",
            "status": "no_data", "total_peaks": 0, "total_patterns": 0,
            "n_matches": 0, "n_signals": 0, "current_stage": "unknown",
        }])

    tf = time_format or "1D"
    min_drop = _MIN_PEAK_DROP_PCT.get(tf, -3.0)

    # 1. Load historical pattern library (filtered by current timeframe)
    try:
        config = load_config()
        storage = AngleStorage(config.data_root)
        historical = storage.read(symbol, angle_name)
    except Exception:
        LOG.warning("Could not read historical data for %s/%s", symbol, angle_name)
        historical = pd.DataFrame()

    library_df = load_pattern_library(historical, time_format=tf)

    # 2. Detect peaks and troughs (true-range ATR — same definition as snapshots)
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr_series = tr.rolling(14).mean()
    atr_val = atr_series.iloc[-1]
    close_last = close.iloc[-1]
    atr_adj = 2.0 * atr_val / close_last * 100 if close_last > 0 and atr_val > 0 else 0
    effective_min_drop = min(min_drop, -atr_adj) if atr_adj > 0 else min_drop

    peaks = detect_peaks(bars, min_drop_pct=min_drop, atr_series=atr_series)
    troughs = detect_troughs(bars, min_rise_pct=-min_drop, atr_series=atr_series)
    peaks, troughs = filter_alternating_inflections(peaks, troughs)

    if not peaks:
        rows.append({
            "analysis_at": now, "angle": angle_name, "type": "summary",
            "status": "no_peaks", "total_peaks": 0, "total_patterns": len(library_df),
            "n_matches": 0, "n_signals": 0, "current_stage": "unknown",
        })
        return pd.DataFrame(rows)

    # 3. Capture snapshots for extrema not yet stored with a MATURE outcome.
    # Rows first stored with a truncated forward window (outcome_mature=False)
    # are recaptured so drawdown/recovery get finalized once more bars exist.
    known_ts = _mature_snapshot_ts(historical, "peak", tf)
    known_trough_ts = _mature_snapshot_ts(historical, "trough", tf)

    indicators_df = compute_indicators(bars)
    all_snapshots = capture_all_peaks(bars, peaks, troughs, peaks, tf=tf, indicators_df=indicators_df)
    new_snapshots = [s for s in all_snapshots if s["bar_ts"] not in known_ts]

    new_troughs = [t for t in troughs if t["bar_ts"] not in known_trough_ts]
    new_trough_snapshots = capture_all_troughs(
        bars, new_troughs, prev_peaks=peaks, tf=tf, indicators_df=indicators_df
    )

    for snap in new_snapshots:
        snap["analysis_at"] = now
        snap["angle"] = angle_name
        snap["symbol"] = symbol
        snap["time_format"] = tf
        rows.append(snap)

    for snap in new_trough_snapshots:
        snap["analysis_at"] = now
        snap["angle"] = angle_name
        snap["symbol"] = symbol
        snap["time_format"] = tf
        rows.append(snap)

    library_after = len(library_df) + len(new_snapshots)

    # 4. Walk-forward matching: pool = historical library + this run's mature
    # snapshots; each query peak only matches peaks with strictly earlier bar_ts.
    matches = []
    recent_matches = []
    recent_snapshot = all_snapshots[-1] if all_snapshots else None
    in_run_df = pd.DataFrame([s for s in all_snapshots if s.get("outcome_mature")])
    pool_parts = [df for df in (library_df, in_run_df) if not df.empty]
    match_pool = pd.concat(pool_parts, ignore_index=True) if pool_parts else pd.DataFrame()
    if not match_pool.empty:
        if "outcome_mature" in match_pool.columns:
            # Keep legacy rows (no flag) and mature rows; drop provisional outcomes
            match_pool = match_pool[
                (match_pool["outcome_mature"].isna()) | (match_pool["outcome_mature"] == True)  # noqa: E712
            ]
        if "bar_ts" in match_pool.columns:
            match_pool = match_pool.drop_duplicates(subset=["bar_ts"], keep="last")
    # Session soft-filter only for intraday formats — daily bars all stamp
    # into one session bucket, so filtering there would be an artifact
    use_session = tf in ("15min", "1H", "4H")
    if len(match_pool) >= 3:
        X, lib_indices, norm_params = build_feature_matrix(match_pool)
        if X.shape[0] > 0:
            matches_by_ts = {}
            for snap in new_snapshots:
                peak_matches = find_similar(
                    snap, match_pool, X, lib_indices, k=5,
                    norm_params=norm_params, before_ts=snap.get("bar_ts"),
                    session=snap.get("session") if use_session else None,
                )
                matches_by_ts[snap.get("bar_ts")] = peak_matches
                for m in peak_matches:
                    m["analysis_at"] = now
                    m["angle"] = angle_name
                    m["query_bar_ts"] = snap.get("bar_ts")
                    rows.append(m)
                matches.extend(peak_matches)
            # Signals must reflect the LATEST peak's matches only
            if recent_snapshot is not None:
                recent_ts = recent_snapshot.get("bar_ts")
                if recent_ts in matches_by_ts:
                    recent_matches = matches_by_ts[recent_ts]
                else:
                    recent_matches = find_similar(
                        recent_snapshot, match_pool, X, lib_indices, k=5,
                        norm_params=norm_params, before_ts=recent_ts,
                        session=recent_snapshot.get("session") if use_session else None,
                    )

    # 5. Classify lifecycle stage
    recent_peaks_sorted = sorted(all_snapshots[-3:], key=lambda x: x.get("bar_idx", 0)) if all_snapshots else []
    recent_trough_list = []
    if troughs:
        for t in troughs:
            ts_val = t["bar_ts"]
            recent_trough_list.append({
                "bar_ts": ts_val,
                "trough_close": t.get("trough_close", bars["close"].iloc[t["idx"]] if t["idx"] < len(bars) else 0),
            })

    high_conf = sum(1 for m in recent_matches if m.get("similarity", 0) > 0.85)
    drawdowns = [m.get("matched_drawdown_pct") for m in recent_matches if m.get("matched_drawdown_pct") is not None]
    avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else None

    lifecycle_result = classify(recent_peaks_sorted, recent_trough_list, high_conf, avg_dd)
    lifecycle_result["analysis_at"] = now
    lifecycle_result["angle"] = angle_name
    lifecycle_result["time_format"] = tf
    rows.append(lifecycle_result)

    # 6. Generate signals from the most recent peak's matches only
    signals = generate_signals(
        recent_matches, lifecycle_result, recent_snapshot, symbol, tf,
        bar_ts=recent_snapshot.get("bar_ts") if recent_snapshot else None,
    )
    for sig in signals:
        sig["analysis_at"] = now
        sig["angle"] = angle_name
        sig["time_format"] = tf
    rows.extend(signals)

    # 7. Summary
    dominant_signal = max(signals, key=lambda s: s.get("confidence", 0))["signal_type"] if signals else None
    rows.append({
        "analysis_at": now,
        "angle": angle_name,
        "type": "summary",
        "status": "completed",
        "time_format": tf,
        "min_drop_threshold": round(effective_min_drop, 1),
        "total_peaks": len(peaks),
        "new_snapshots": len(new_snapshots),
        "total_patterns": library_after,
        "n_matches": len(matches),
        "n_signals": len(signals),
        "current_stage": lifecycle_result.get("stage"),
        "current_risk": lifecycle_result.get("risk"),
        "dominant_signal": dominant_signal,
    })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
