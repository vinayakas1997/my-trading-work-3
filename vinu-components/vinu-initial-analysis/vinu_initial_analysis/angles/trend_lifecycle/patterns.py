"""Pattern library — load historical snapshots, normalize, KNN matching.

The pattern library accumulates naturally: every run reads ALL historical
snapshots from AngleStorage, deduplicates by bar_ts, and grows the library.
No separate storage infrastructure needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import numpy as np

LOG = logging.getLogger(__name__)

_MIN_SESSION_POOL = 10

_FEATURE_COLS = [
    "close_sma_9_pct", "close_sma_50_pct", "close_sma_200_pct",
    "rsi_14", "rsi_7",
    "atr_pct", "bb_width_pct",
    "volume_ratio_20", "volume_zscore_20",
    "runup_bars", "internal_dips_count", "relaxation_bars",
    "upper_wick_pct", "body_size_pct",
    "peak_ratio",
    "daily_return",
    "rsi_divergence", "adx_slope_5",
]


def load_pattern_library(library_df: pd.DataFrame, time_format: str | None = None) -> pd.DataFrame:
    """Deduplicate and prepare the pattern library from historical snapshot rows.

    Removes rows with missing critical features, deduplicates by bar_ts.
    Optionally filters by time_format so hourly peaks don't match daily peaks.
    """
    if library_df.empty:
        return pd.DataFrame()
    peak_snapshots = library_df[
        (library_df.get("type") == "snapshot")
        & (library_df.get("inflection_type") == "peak")
    ].copy()
    if peak_snapshots.empty:
        return pd.DataFrame()
    if time_format is not None and "time_format" in peak_snapshots.columns:
        peak_snapshots = peak_snapshots[
            (peak_snapshots["time_format"].isna()) | (peak_snapshots["time_format"] == time_format)
        ]
    if peak_snapshots.empty:
        return pd.DataFrame()
    if "bar_ts" in peak_snapshots.columns:
        peak_snapshots = peak_snapshots.drop_duplicates(subset=["bar_ts"], keep="last")
    return peak_snapshots


def build_feature_matrix(library_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict | None]:
    """Build normalized feature matrix from the library.

    Returns (normalized feature matrix, original indices, norm_params dict).
    Norm params contain 'mean' and 'std' vectors for transforming queries later.
    Columns that are ALL NaN are excluded. Remaining NaN values are filled with column median.
    """
    library_df = library_df.copy()
    # Legacy rows stored raw-dollar atr_14; derive the scale-invariant atr_pct
    if "atr_pct" not in library_df.columns and {"atr_14", "peak_close"}.issubset(library_df.columns):
        with np.errstate(divide="ignore", invalid="ignore"):
            library_df["atr_pct"] = (
                library_df["atr_14"].astype(float) / library_df["peak_close"].astype(float).replace(0, np.nan)
            )
    available = [c for c in _FEATURE_COLS if c in library_df.columns]
    subset = library_df[available].copy()
    cols_to_drop = [c for c in subset.columns if subset[c].isna().all()]
    if cols_to_drop:
        subset = subset.drop(columns=cols_to_drop)
    if subset.empty or subset.shape[1] == 0:
        return np.array([]), np.array([]), None
    subset = subset.fillna(subset.median())
    X = subset.values.astype(np.float64)
    mask = np.all(np.isfinite(X), axis=1)
    X = X[mask]
    indices = subset.index[mask].values
    if X.shape[0] == 0:
        return np.array([]), np.array([]), None
    mean_ = X.mean(axis=0)
    std_ = X.std(axis=0) + 1e-10
    X_norm = (X - mean_) / std_
    norm_params = {"mean": mean_, "std": std_, "columns": subset.columns.tolist()}
    return X_norm, indices, norm_params


def find_similar(
    query_snapshot: dict,
    library_df: pd.DataFrame,
    X_norm: np.ndarray,
    lib_indices: np.ndarray,
    k: int = 5,
    norm_params: dict | None = None,
    before_ts: int | None = None,
    session: str | None = None,
) -> list[dict]:
    """Find top-k most similar patterns from the library using cosine similarity.

    Query is z-score normalized using the same mean/std as the library (norm_params).
    When before_ts is given, only library rows with bar_ts strictly earlier are
    considered (walk-forward: a peak can only match peaks that came before it).
    When session is given, candidates are SOFT-filtered to the same session —
    applied only if at least _MIN_SESSION_POOL candidates remain, otherwise the
    full pool is used so a small library is never starved.
    Returns list of dicts with matched peak info, similarity score, and historical outcome.
    """
    if norm_params is None:
        available = [c for c in _FEATURE_COLS if c in query_snapshot and query_snapshot[c] is not None]
    else:
        available = [c for c in norm_params["columns"] if c in query_snapshot and query_snapshot[c] is not None]
    if not available or X_norm.shape[0] == 0:
        return []
    query_vec = np.array([float(query_snapshot[c]) for c in available], dtype=np.float64)
    if not np.all(np.isfinite(query_vec)):
        return []
    # Z-score normalize query using library stats
    if norm_params is not None:
        col_map = {col: i for i, col in enumerate(norm_params["columns"])}
        mean_vec = np.array([norm_params["mean"][col_map[c]] for c in available])
        std_vec = np.array([norm_params["std"][col_map[c]] for c in available])
        query_vec = (query_vec - mean_vec) / std_vec
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    # Find the matching columns in X_norm
    lib_cols = norm_params["columns"] if norm_params else _FEATURE_COLS
    col_indices = [i for i, c in enumerate(lib_cols) if c in available]
    if not col_indices:
        return []
    X_sub = X_norm[:, col_indices]
    valid_mask = np.all(np.isfinite(X_sub), axis=1)
    if valid_mask.sum() == 0:
        return []
    X_sub = X_sub[valid_mask]
    lib_idx_sub = lib_indices[valid_mask]
    if before_ts is not None and "bar_ts" in library_df.columns:
        ts_vals = library_df.loc[lib_idx_sub, "bar_ts"].astype("int64").values
        ts_mask = ts_vals < int(before_ts)
        if ts_mask.sum() == 0:
            return []
        X_sub = X_sub[ts_mask]
        lib_idx_sub = lib_idx_sub[ts_mask]
    if session is not None and "session" in library_df.columns:
        session_vals = library_df.loc[lib_idx_sub, "session"].values
        session_mask = session_vals == session
        # Soft filter: only apply when enough same-session candidates remain
        if session_mask.sum() >= _MIN_SESSION_POOL:
            X_sub = X_sub[session_mask]
            lib_idx_sub = lib_idx_sub[session_mask]
    X_norm_sub = X_sub / (np.linalg.norm(X_sub, axis=1, keepdims=True) + 1e-10)
    similarities = np.dot(X_norm_sub, q_norm)
    top_k = min(k, len(similarities))
    if top_k == 0:
        return []
    best_idx = np.argsort(-similarities)[:top_k]
    matches = []
    for idx_in_result in best_idx:
        lib_row = library_df.loc[lib_idx_sub[idx_in_result]]
        match = {
            "type": "match",
            "matched_bar_ts": int(lib_row.get("bar_ts", 0)),
            "similarity": round(float(similarities[idx_in_result]), 4),
            "matched_drawdown_pct": float(lib_row.get("drawdown_pct")) if pd.notna(lib_row.get("drawdown_pct", np.nan)) else None,
            "matched_recovery_bars": int(lib_row.get("recovery_time_bars")) if pd.notna(lib_row.get("recovery_time_bars", np.nan)) else None,
        }
        matches.append(match)
    return matches


def get_library_stats(library_df: pd.DataFrame) -> dict:
    """Get summary stats about the pattern library."""
    if library_df.empty:
        return {"total_peaks": 0, "n_clusters": 0}
    return {
        "total_peaks": len(library_df),
    }
