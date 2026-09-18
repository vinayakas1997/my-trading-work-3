"""High-expectations spec #6: a whole-market analogue of the existing
per-symbol KNN pattern-matching engine (vinu-initial-analysis/.../
trend_lifecycle/patterns.py), plus the aggregate outcome stats that
engine's get_library_stats() doesn't have -- positive/negative match
counts, avg/median return, max drawdown across matches.

This is a parallel implementation of patterns.py's KNN-cosine-similarity
primitives (build_feature_matrix/find_similar), NOT a direct import of
them: vinu-research and vinu-initial-analysis are separate, isolated
services in this codebase -- confirmed by vinu-research/Dockerfile only
installing vinu-infra/vinu-stock-price/vinu-tools/vinu-simulator (never
vinu-initial-analysis), and by the same cross-service isolation boundary
vinu-live's orchestrator.py documents explicitly for vinu_research.models.
Every inter-service data path here goes through ResearchTools' HTTP calls,
same as fetch_risk_state/fetch_personality_features already do -- a direct
Python import across that boundary would be new, unprecedented coupling.
The KNN logic itself (z-score normalize, cosine similarity, before_ts
walk-forward filter, top-k) is small and generic enough to vendor rather
than stand up a new HTTP endpoint for it.

Feature set is a documented SUBSET of patterns._FEATURE_COLS's naming
-- only the ones computable from a single close-price series (no OHLC/
volume exists for a synthetic market index reconstructed from
ResearchTools.get_benchmark_data's period-returns output):
close_sma_9_pct, close_sma_50_pct, close_sma_200_pct, rsi_14, rsi_7,
atr_pct (proxy: rolling realized-vol of returns, not a true high-low ATR),
bb_width_pct, daily_return, runup_bars (window length in bars, a
structural proxy, not the per-symbol peak-lifecycle metric patterns.py
computes).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from vinu_research.regime_windows import derive_regime_windows

if TYPE_CHECKING:
    from vinu_research.tools import ResearchTools

LOG = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_CHUNK_DAYS = 365
_DEFAULT_STEP_DAYS = 90
DEFAULT_OUTCOME_HORIZON_DAYS = 20

# Vendored subset of patterns._FEATURE_COLS -- see module docstring for why
# this isn't a cross-service import of that list.
_MARKET_FEATURE_COLS = [
    "close_sma_9_pct", "close_sma_50_pct", "close_sma_200_pct",
    "rsi_14", "rsi_7", "atr_pct", "bb_width_pct",
    "daily_return", "runup_bars",
]


def _ensure_datetime_index(s: pd.Series) -> pd.Series | None:
    s = s.dropna().sort_index()
    if not isinstance(s.index, pd.DatetimeIndex):
        try:
            s = s.copy()
            s.index = pd.to_datetime(s.index)
        except Exception:
            return None
    return s


def derive_market_regime_windows(
    index_series: pd.Series | None,
    *,
    min_window_days: int = 15,
    decline_window_days: int = 30,
    lookback_chunk_days: int = _DEFAULT_LOOKBACK_CHUNK_DAYS,
    step_days: int = _DEFAULT_STEP_DAYS,
) -> list[tuple[str, str, str]]:
    """Thin wrapper around regime_windows.derive_regime_windows (already
    generic over "a single series," per its own docstring), fed a market
    index instead of one symbol.

    derive_regime_windows alone only returns the *global* extrema (one
    drawdown, one runup, one steepest decline) for whatever series it's
    given -- a 3-window "library" isn't useful to match against. This calls
    it repeatedly over overlapping trailing chunks of `index_series` (a
    `lookback_chunk_days`-long span advanced every `step_days`) so many
    historical regime windows accumulate, deduplicated by (from, to) --
    matching the spirit of patterns.py's "the library accumulates
    naturally" without a new storage layer.
    """
    s = _ensure_datetime_index(index_series) if index_series is not None else None
    if s is None or s.empty:
        return []

    windows: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _collect(chunk_series: pd.Series) -> None:
        for name, f, t in derive_regime_windows(
            chunk_series, min_window_days=min_window_days, decline_window_days=decline_window_days,
        ):
            if (f, t) not in seen:
                seen.add((f, t))
                windows.append((name, f, t))

    chunk = pd.Timedelta(days=lookback_chunk_days)
    step = pd.Timedelta(days=step_days)
    chunk_start = s.index[0]
    end_of_data = s.index[-1]
    while chunk_start + chunk <= end_of_data:
        _collect(s[(s.index >= chunk_start) & (s.index <= chunk_start + chunk)])
        chunk_start += step

    # Always also run over the full series once, so a final partial chunk
    # (shorter than lookback_chunk_days) is never lost entirely.
    _collect(s)

    return windows


def _rsi(returns: pd.Series, window: int) -> pd.Series:
    gains = returns.clip(lower=0.0)
    losses = -returns.clip(upper=0.0)
    avg_gain = gains.rolling(window).mean()
    avg_loss = losses.rolling(window).mean()
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def _window_features_at(
    s: pd.Series,
    returns: pd.Series,
    sma_9: pd.Series,
    sma_50: pd.Series,
    sma_200: pd.Series,
    rolling_std_20: pd.Series,
    rsi_14: pd.Series,
    rsi_7: pd.Series,
    from_date: str,
    to_date: str,
) -> dict[str, Any] | None:
    """Features as of `to_date`, computed from trailing history only up to
    and including that date -- walk-forward safe by construction, the same
    posture find_similar's before_ts filter gives the per-symbol case."""
    end_ts = pd.Timestamp(to_date)
    pos = s.index.searchsorted(end_ts, side="right") - 1
    if pos < 0 or pos >= len(s):
        return None
    end_actual = s.index[pos]
    close = float(s.iloc[pos])

    def _pct_vs(sma: pd.Series) -> float | None:
        val = sma.iloc[pos]
        if pd.isna(val) or val == 0:
            return None
        return float(close / val - 1.0)

    bars_in_window = int(((s.index >= pd.Timestamp(from_date)) & (s.index <= end_actual)).sum())
    bb_mid = sma_50.iloc[pos] if pos < len(sma_50) else np.nan
    bb_width_pct = (
        float(rolling_std_20.iloc[pos] / bb_mid) if pd.notna(bb_mid) and bb_mid != 0 and pd.notna(rolling_std_20.iloc[pos])
        else None
    )

    return {
        "bar_ts": int(end_actual.value),
        "from_date": from_date,
        "to_date": to_date,
        "close_sma_9_pct": _pct_vs(sma_9),
        "close_sma_50_pct": _pct_vs(sma_50),
        "close_sma_200_pct": _pct_vs(sma_200),
        "rsi_14": float(rsi_14.iloc[pos]) if pos < len(rsi_14) else None,
        "rsi_7": float(rsi_7.iloc[pos]) if pos < len(rsi_7) else None,
        # Proxy: rolling realized-vol of returns, not a true high-low ATR --
        # no OHLC exists for a market index built from a returns series.
        "atr_pct": float(rolling_std_20.iloc[pos]) if pos < len(rolling_std_20) and pd.notna(rolling_std_20.iloc[pos]) else None,
        "bb_width_pct": bb_width_pct,
        "daily_return": float(returns.iloc[pos]) if pos < len(returns) and pd.notna(returns.iloc[pos]) else None,
        # Structural proxy: window length in trading days, not the
        # per-symbol peak-lifecycle metric patterns.py computes.
        "runup_bars": bars_in_window,
    }


def build_market_feature_table(
    index_series: pd.Series | None,
    windows: list[tuple[str, str, str]],
) -> pd.DataFrame:
    """One row per window (keyed by window-id, i.e. row position -- not
    symbol+bar_ts), using the feature subset documented at module level.
    Empty DataFrame when there's no usable series or no windows.
    """
    s = _ensure_datetime_index(index_series) if index_series is not None else None
    if s is None or s.empty or not windows:
        return pd.DataFrame()

    returns = s.pct_change()
    sma_9 = s.rolling(9).mean()
    sma_50 = s.rolling(50).mean()
    sma_200 = s.rolling(200).mean()
    rolling_std_20 = returns.rolling(20).std()
    rsi_14 = _rsi(returns, 14)
    rsi_7 = _rsi(returns, 7)

    rows = []
    for name, from_date, to_date in windows:
        row = _window_features_at(
            s, returns, sma_9, sma_50, sma_200, rolling_std_20, rsi_14, rsi_7, from_date, to_date,
        )
        if row is not None:
            row["window_name"] = name
            rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def build_outcome_lookup(
    index_series: pd.Series | None,
    table: pd.DataFrame,
    horizon_days: int = DEFAULT_OUTCOME_HORIZON_DAYS,
) -> dict[int, float]:
    """Maps each row's bar_ts (the same int64 key find_similar's matches
    report as matched_bar_ts) to the realized forward return over the next
    `horizon_days` trading bars after that window's end -- the "did this
    historical analogue turn out well" signal get_market_regime_stats
    aggregates. Empty dict when a window is too close to the end of
    `index_series` for a full forward horizon to exist yet.
    """
    s = _ensure_datetime_index(index_series) if index_series is not None else None
    if s is None or s.empty or table.empty:
        return {}
    lookup: dict[int, float] = {}
    for _, row in table.iterrows():
        bar_ts = int(row["bar_ts"])
        end_ts = pd.Timestamp(bar_ts)
        pos = s.index.searchsorted(end_ts, side="right") - 1
        if pos < 0 or pos + horizon_days >= len(s):
            continue
        start_price = float(s.iloc[pos])
        end_price = float(s.iloc[pos + horizon_days])
        if start_price == 0:
            continue
        lookup[bar_ts] = end_price / start_price - 1.0
    return lookup


def _build_feature_matrix(table: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict | None]:
    """Vendored copy of patterns.build_feature_matrix's z-score-normalize
    logic (see module docstring for why this isn't a cross-service import),
    over _MARKET_FEATURE_COLS instead of patterns._FEATURE_COLS. Returns
    (normalized feature matrix, original indices, norm_params)."""
    available = [c for c in _MARKET_FEATURE_COLS if c in table.columns]
    subset = table[available].copy()
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


def _find_similar(
    query_features: dict[str, Any],
    table: pd.DataFrame,
    X_norm: np.ndarray,
    indices: np.ndarray,
    k: int,
    norm_params: dict | None,
    before_ts: int | None,
) -> list[dict]:
    """Vendored copy of patterns.find_similar's cosine-similarity KNN +
    before_ts walk-forward filter (see module docstring). Returns match dicts
    shaped like patterns.find_similar's ("type", "matched_bar_ts",
    "similarity"), without the per-symbol-only matched_drawdown_pct/
    matched_recovery_bars fields -- get_market_regime_stats below reads
    realized outcomes from a separate outcome_lookup instead."""
    if norm_params is None:
        available = [c for c in _MARKET_FEATURE_COLS if c in query_features and query_features[c] is not None]
    else:
        available = [c for c in norm_params["columns"] if c in query_features and query_features[c] is not None]
    if not available or X_norm.shape[0] == 0:
        return []
    query_vec = np.array([float(query_features[c]) for c in available], dtype=np.float64)
    if not np.all(np.isfinite(query_vec)):
        return []
    if norm_params is not None:
        col_map = {col: i for i, col in enumerate(norm_params["columns"])}
        mean_vec = np.array([norm_params["mean"][col_map[c]] for c in available])
        std_vec = np.array([norm_params["std"][col_map[c]] for c in available])
        query_vec = (query_vec - mean_vec) / std_vec
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    lib_cols = norm_params["columns"] if norm_params else _MARKET_FEATURE_COLS
    col_indices = [i for i, c in enumerate(lib_cols) if c in available]
    if not col_indices:
        return []
    X_sub = X_norm[:, col_indices]
    valid_mask = np.all(np.isfinite(X_sub), axis=1)
    if valid_mask.sum() == 0:
        return []
    X_sub = X_sub[valid_mask]
    idx_sub = indices[valid_mask]
    if before_ts is not None and "bar_ts" in table.columns:
        ts_vals = table.loc[idx_sub, "bar_ts"].astype("int64").values
        ts_mask = ts_vals < int(before_ts)
        if ts_mask.sum() == 0:
            return []
        X_sub = X_sub[ts_mask]
        idx_sub = idx_sub[ts_mask]
    X_norm_sub = X_sub / (np.linalg.norm(X_sub, axis=1, keepdims=True) + 1e-10)
    similarities = np.dot(X_norm_sub, q_norm)
    top_k = min(k, len(similarities))
    if top_k == 0:
        return []
    best_idx = np.argsort(-similarities)[:top_k]
    matches = []
    for idx_in_result in best_idx:
        row = table.loc[idx_sub[idx_in_result]]
        matches.append({
            "type": "match",
            "matched_bar_ts": int(row.get("bar_ts", 0)),
            "similarity": round(float(similarities[idx_in_result]), 4),
        })
    return matches


def find_similar_market_regimes(
    query_features: dict[str, Any],
    table: pd.DataFrame,
    k: int = 5,
    before_ts: int | None = None,
) -> list[dict]:
    """Cosine-similarity KNN over `table` (see _build_feature_matrix/
    _find_similar above -- a vendored copy of patterns.py's generic KNN
    primitives, not a cross-service import; see module docstring).
    `before_ts` preserves the same walk-forward guarantee the per-symbol
    engine has (a window can only match windows that came before it)."""
    if table.empty:
        return []
    X_norm, indices, norm_params = _build_feature_matrix(table)
    if X_norm.shape[0] == 0:
        return []
    return _find_similar(query_features, table, X_norm, indices, k, norm_params, before_ts)


def get_market_regime_stats(
    matches: list[dict],
    outcome_lookup: dict[int, float],
) -> dict[str, Any]:
    """The aggregate stats get_library_stats() (per-symbol) doesn't have:
    n_matches, n_positive, n_negative, positive_ratio, avg_return,
    median_return, max_drawdown across the matched windows' realized
    forward returns (from `outcome_lookup`, see build_outcome_lookup).

    A match with no entry in outcome_lookup (window too recent for a full
    forward horizon) is skipped, not treated as zero -- silently including
    it would understate the drawdown/return spread instead of just
    reporting on fewer matches.
    """
    outcomes = [outcome_lookup[m["matched_bar_ts"]] for m in matches if m.get("matched_bar_ts") in outcome_lookup]
    if not outcomes:
        return {
            "n_matches": 0, "n_positive": 0, "n_negative": 0, "positive_ratio": 0.0,
            "avg_return": 0.0, "median_return": 0.0, "max_drawdown": 0.0,
        }
    n = len(outcomes)
    n_positive = sum(1 for o in outcomes if o > 0)
    n_negative = sum(1 for o in outcomes if o < 0)
    return {
        "n_matches": n,
        "n_positive": n_positive,
        "n_negative": n_negative,
        "positive_ratio": n_positive / n,
        "avg_return": float(np.mean(outcomes)),
        "median_return": float(np.median(outcomes)),
        "max_drawdown": float(min(outcomes)),
    }


_DAY_CACHE: dict[str, dict[str, Any]] = {}
_DEFAULT_LOOKBACK_DAYS = 5 * 365
_DEFAULT_QUERY_WINDOW_DAYS = 60


async def get_market_regime_stats_for_today(
    tools: "ResearchTools",
    *,
    benchmark_symbol: str = "SPY",
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
    query_window_days: int = _DEFAULT_QUERY_WINDOW_DAYS,
    k: int = 5,
    outcome_horizon_days: int = DEFAULT_OUTCOME_HORIZON_DAYS,
    history_store: Any | None = None,
) -> dict[str, Any]:
    """Full pipeline: fetch `benchmark_symbol`'s returns -> reconstruct a
    price path -> derive historical regime windows -> match the most recent
    `query_window_days` against them -> aggregate outcome stats.

    This is a market-wide computation, not a per-symbol one -- every
    author_trade_plan() call on the same calendar day gets the identical
    result, so it's cached per day (module-level, process-lifetime) rather
    than recomputed on every trade-plan authoring call. Fails open to {}
    (never raises) on any fetch or compute problem, same posture as
    fetch_risk_state/fetch_personality_features -- a missing regime context
    just means compute_trade_score's regime_fit_score defaults to 0, not
    that authoring breaks.

    `history_store` (a MarketRegimeHistoryStore, optional) durably records
    the result the first time it's computed each day -- see
    storage/market_regime_history.py for why the in-memory day-cache alone
    isn't enough for reflection's analysis J to read a trend from. None
    (the default) preserves the previous no-persistence behavior exactly.
    """
    cache_key = datetime.now(timezone.utc).date().isoformat()
    cached = _DAY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    result: dict[str, Any] = {}
    try:
        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=lookback_days)
        returns = await tools.get_benchmark_data(benchmark_symbol, str(from_date), str(to_date))
        if returns is not None and len(returns) >= query_window_days + 20:
            price = (1.0 + returns.fillna(0.0)).cumprod()
            windows = derive_market_regime_windows(price)
            table = build_market_feature_table(price, windows)
            outcomes = build_outcome_lookup(price, table, horizon_days=outcome_horizon_days)

            query_start_pos = max(0, len(price) - query_window_days)
            query_window = [(
                "query",
                price.index[query_start_pos].strftime("%Y-%m-%d"),
                price.index[-1].strftime("%Y-%m-%d"),
            )]
            query_table = build_market_feature_table(price, query_window)
            if not query_table.empty:
                query_row = query_table.iloc[0].to_dict()
                matches = find_similar_market_regimes(
                    query_row, table, k=k, before_ts=query_row["bar_ts"],
                )
                result = get_market_regime_stats(matches, outcomes)
    except Exception as e:
        LOG.warning("get_market_regime_stats_for_today(%s) failed: %s", benchmark_symbol, e)
        result = {}

    _DAY_CACHE.clear()  # only ever keep today's entry
    _DAY_CACHE[cache_key] = result
    if history_store is not None and result:
        try:
            history_store.record(cache_key, result)
        except Exception as e:
            LOG.warning("MarketRegimeHistoryStore.record(%s) failed: %s", cache_key, e)
    return result
