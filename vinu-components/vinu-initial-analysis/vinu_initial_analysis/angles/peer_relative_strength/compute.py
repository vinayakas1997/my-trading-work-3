"""Peer Relative Strength — continuous rolling peer co-movement & excess return."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ROLLING_CORR_WINDOW = 63
RELATIVE_RETURN_DAYS = 20
SAMPLE_EVERY_N_BARS = 5


def _empty_result(symbol: str, status: str, **extra: Any) -> pd.DataFrame:
    row: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": datetime.now(timezone.utc).isoformat(),
        "angle": "peer_relative_strength",
        "status": status,
    }
    row.update(extra)
    return pd.DataFrame([row])


def _to_daily_close_series(raw: pd.DataFrame | None) -> pd.Series | None:
    if raw is None or raw.empty or "close" not in raw.columns or "bar_ts" not in raw.columns:
        return None
    ts = pd.to_numeric(raw["bar_ts"], errors="coerce").dropna().astype("int64")
    idx = pd.to_datetime(ts.to_numpy(), unit="s").tz_localize("UTC")
    out = pd.Series(raw["close"].astype(float).values, index=idx)
    out = out.sort_index()
    return out.groupby(out.index).last()


def _aligned_closes(
    symbol: str,
    bars: pd.DataFrame,
    from_ts: int | None,
    to_ts: int | None,
    price_client: Any,
) -> pd.DataFrame:
    """Daily closes for symbol + watchlist peers, aligned on a common dated index."""
    series_map: dict[str, pd.Series] = {}

    own = _to_daily_close_series(bars)
    if own is None:
        return pd.DataFrame()
    series_map[symbol.upper()] = own

    peer_set: set[str] = {symbol.upper()}
    try:
        if price_client is not None:
            watch = price_client.get_watchlist()
            if watch:
                peer_set = set(w.upper() for w in watch) | {symbol.upper()}
    except Exception:
        pass

    for sym in sorted(peer_set):
        if sym == symbol.upper():
            continue
        try:
            candles = price_client.get_candles(
                sym, from_ts=from_ts, to_ts=to_ts, interval="1D", limit=50000,
            )
        except Exception:
            candles = []
        s = _to_daily_close_series(pd.DataFrame(candles) if candles else pd.DataFrame())
        if s is not None and not s.empty:
            series_map[sym] = s

    df = pd.DataFrame(series_map)
    if df.shape[1] < 2:
        return pd.DataFrame()
    return df.sort_index().ffill()


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
        return _empty_result(symbol, "no_data")

    aligned = _aligned_closes(symbol, bars, from_ts, to_ts, price_client)
    peers = [c for c in aligned.columns if c.upper() != symbol.upper()]
    if len(aligned) < 1 or not peers:
        return _empty_result(
            symbol, "no_peers" if not peers else "insufficient_data",
            n_observations=int(len(aligned)) if len(aligned) else 0, n_peers=len(peers),
        )
    if len(aligned) < ROLLING_CORR_WINDOW + 2:
        return _empty_result(symbol, "insufficient_data", n_observations=int(len(aligned)))

    analysis_at = datetime.now(timezone.utc).isoformat()
    returns = aligned.astype(float).pct_change()

    own = symbol.upper()
    basket_return = returns[peers].mean(axis=1)
    rel_ret = (returns[own].rolling(RELATIVE_RETURN_DAYS).sum()
               - basket_return.rolling(RELATIVE_RETURN_DAYS).sum())

    rows: list[dict[str, Any]] = []
    for peer in peers:
        corr = returns[own].rolling(ROLLING_CORR_WINDOW).corr(returns[peer])
        corr = corr[corr.notna()]
        sampled_indices = corr.index[::SAMPLE_EVERY_N_BARS]
        for idx in sampled_indices:
            corr_val = corr.loc[idx]
            rr = rel_ret.get(idx)
            if pd.isna(corr_val):
                continue
            rows.append({
                "symbol": symbol,
                "analysis_at": analysis_at,
                "angle": "peer_relative_strength",
                "date": idx.strftime("%Y-%m-%d"),
                "bar_ts": int(idx.timestamp()),
                "peer_symbol": peer,
                "correlation": float(corr_val),
                "relative_return_20d": float(rr) if pd.notna(rr) else None,
            })

    if not rows:
        return _empty_result(symbol, "insufficient_data", n_observations=int(len(aligned)))

    return pd.DataFrame(rows)