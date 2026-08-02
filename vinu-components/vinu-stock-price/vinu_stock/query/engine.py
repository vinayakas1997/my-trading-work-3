"""Candle query engine over Parquet archive + live.

The full dataset per symbol is loaded once into an in-memory frame (it is only
a few MB per symbol).  Parquet is only re-read when the underlying files change
(live ingest appends).  Range filtering and interval aggregation happen in
pandas, so steady-state candle queries are milliseconds.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import duckdb

from vinu_stock.query.aggregate import aggregate_bars, interval_to_seconds
from vinu_stock.query.cache import get_cache
from vinu_stock.query.indicators import apply_adjusted_prices, apply_indicators
from vinu_stock.storage.paths import parquet_globs

# symbol -> (file_signature, pandas DataFrame, last_signature_check_monotonic)
_CACHED_FRAMES: dict[str, tuple[tuple, Any, float]] = {}
_FRAME_LOCK = threading.Lock()
_SIGNATURE_COOLDOWN_SEC = 30.0


def _file_signature(patterns: list[str]) -> tuple:
    """Signature of parquet files (path + mtime + size) for cache invalidation."""
    sig: list[tuple] = []
    for pattern in patterns:
        try:
            for p in sorted(Path(pattern).parent.glob(Path(pattern).name)):
                st = p.stat()
                sig.append((str(p), st.st_mtime_ns, st.st_size))
        except OSError:
            continue
    return tuple(sig)


def _load_symbol_frame(data_root: Path, symbol: str) -> Any:
    """Return a deduped in-memory frame of the full symbol dataset (cached)."""
    sym = symbol.strip().upper()
    patterns = parquet_globs(data_root, sym)
    if not patterns:
        return None

    now = time.monotonic()
    with _FRAME_LOCK:
        cached = _CACHED_FRAMES.get(sym)
        if cached is not None and (now - cached[2]) < _SIGNATURE_COOLDOWN_SEC:
            return cached[1]

    sig = _file_signature(patterns)
    with _FRAME_LOCK:
        cached = _CACHED_FRAMES.get(sym)
        if cached is not None and cached[0] == sig:
            _CACHED_FRAMES[sym] = (cached[0], cached[1], now)
            return cached[1]

    placeholders = ", ".join(f"'{p}'" for p in patterns)
    conn = duckdb.connect()
    try:
        df = conn.execute(
            f"""
            SELECT symbol, provider, bar_ts, open, high, low, close, volume,
                   COALESCE(adj_factor, 1.0) AS adj_factor
            FROM read_parquet([{placeholders}], union_by_name=true)
            WHERE symbol = ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol, provider, bar_ts ORDER BY bar_ts DESC) = 1
            """,
            [sym],
        ).fetchdf()
    finally:
        conn.close()

    if df is not None and not df.empty:
        df["bar_ts"] = df["bar_ts"].astype("int64")
        df["adj_factor"] = df["adj_factor"].astype("float64")

    with _FRAME_LOCK:
        _CACHED_FRAMES[sym] = (sig, df, now)
    return df


def invalidate_symbol_cache(symbol: str | None = None) -> None:
    with _FRAME_LOCK:
        if symbol is None:
            _CACHED_FRAMES.clear()
        else:
            _CACHED_FRAMES.pop(symbol.strip().upper(), None)


def fetch_candles(
    data_root: Path,
    symbol: str,
    *,
    interval: str = "1m",
    from_ts: int | None = None,
    to_ts: int | None = None,
    provider: str | None = None,
    limit: int = 5000,
    indicators: list[str] | None = None,
    adjusted: bool = True,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> list[dict]:
    sym = symbol.strip().upper()
    df = _load_symbol_frame(data_root, sym)
    if df is None or df.empty:
        return []

    mask = df["symbol"] == sym
    if from_ts is not None:
        mask &= df["bar_ts"] >= from_ts
    if to_ts is not None:
        mask &= df["bar_ts"] <= to_ts
    if provider:
        mask &= df["provider"] == provider.strip().lower()
    sub = df[mask].sort_values("bar_ts")

    is_raw = interval.lower() == "1m"
    if is_raw:
        rows = sub.to_dict(orient="records")
        for rec in rows:
            rec["bar_ts"] = int(rec["bar_ts"])
            rec["adj_factor"] = float(rec.get("adj_factor", 1.0) or 1.0)
        records = rows[:limit]
        if adjusted:
            records = apply_adjusted_prices(records)
    else:
        rows = sub.to_dict(orient="records")
        for rec in rows:
            rec["bar_ts"] = int(rec["bar_ts"])
            rec["adj_factor"] = float(rec.get("adj_factor", 1.0) or 1.0)
        if adjusted:
            adjusted_rows = []
            for rec in rows:
                factor = float(rec.get("adj_factor", 1.0) or 1.0)
                if factor != 1.0:
                    rec = dict(rec)
                    for key in ("open", "high", "low", "close"):
                        if rec[key] is not None:
                            rec[key] = float(rec[key]) * factor
                    rec["adj_factor"] = 1.0
                adjusted_rows.append(rec)
            rows = adjusted_rows
        records = aggregate_bars(rows, interval)[:limit]

    if indicators:
        indicator_set = frozenset(indicators)
        cache = get_cache()
        cached = cache.get(sym, interval, from_ts, to_ts, indicator_set, adjusted)
        if cached is not None:
            records = cached
        else:
            records = apply_indicators(records, indicators)
            cache.set(sym, interval, from_ts, to_ts, indicator_set, adjusted, records)
    return records
