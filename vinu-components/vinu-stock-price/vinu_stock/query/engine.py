"""Candle query engine over Parquet archive + live.

The full dataset per symbol is loaded once into an in-memory frame (it is only
a few MB per symbol).  Parquet is only re-read when the underlying files change
(live ingest appends).  Range filtering and interval aggregation happen in
pandas, so steady-state candle queries are milliseconds.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import warnings
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.parquet as pq

from vinu_infra.sessions import TRADABLE_SESSIONS, parse_sessions, session_mask, spec_of
from vinu_stock.query.aggregate import aggregate_bars, bucket_end, interval_to_seconds
from vinu_stock.query.cache import get_cache
from vinu_stock.query.indicators import apply_adjusted_prices, apply_indicators
from vinu_stock.storage.paths import parquet_globs

LOG = logging.getLogger(__name__)

# symbol -> (file_signature, pandas DataFrame, last_signature_check_monotonic)
_CACHED_FRAMES: dict[str, tuple[tuple, Any, float]] = {}
_FRAME_LOCK = threading.Lock()

# How many parquet loads may run at once, and the memory each DuckDB connection may use (env-tunable).
_LOAD_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get("VINU_STOCK_MAX_CONCURRENT_LOADS", "2"))))
_LOAD_MEMORY_LIMIT = os.environ.get("VINU_STOCK_LOAD_MEMORY_LIMIT", "512MB")
_LOAD_THREADS = max(1, int(os.environ.get("VINU_STOCK_LOAD_THREADS", "2")))
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


def _expand_and_validate(patterns: list[str]) -> tuple[list[str], list[str]]:
    """Expand glob patterns to individual files and split them into
    (readable, unreadable) by opening each file's own parquet footer.

    Reading just the footer (not the row data) is cheap and is enough to
    catch a truncated/partial-write file -- the exact failure mode found
    twice in this project's real live-ingest data (known-issues.md #2).
    Validating per-file, rather than handing the whole glob to a single
    read_parquet([...]) call, is what lets one bad file get skipped
    instead of failing every query for the whole symbol.
    """
    good: list[str] = []
    bad: list[str] = []
    for pattern in patterns:
        try:
            files = sorted(Path(pattern).parent.glob(Path(pattern).name))
        except OSError:
            continue
        for p in files:
            try:
                pq.ParquetFile(p)
                good.append(str(p))
            except Exception:
                bad.append(str(p))
    return good, bad


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

    good_files, bad_files = _expand_and_validate(patterns)
    if bad_files:
        # A `warnings.warn` alone is easy to lose in production (filtered,
        # deduped-per-location, or simply not surfaced by whatever captures
        # stdout) -- this is real data-quality signal (a symbol silently
        # missing data due to file corruption), so it also goes through the
        # normal logging pipeline where it's actually queryable.
        LOG.warning(
            "Skipping %d unreadable parquet file(s) for %s: %s", len(bad_files), sym, bad_files,
        )
        warnings.warn(
            f"Skipping {len(bad_files)} unreadable parquet file(s) for {sym}: {bad_files}",
            RuntimeWarning,
            stacklevel=2,
        )

    df = None
    if good_files:
        placeholders = ", ".join(f"'{p}'" for p in good_files)
        # Every load used to open its own unbounded DuckDB connection, all at once: a burst (the analysis service
        # restarting for 50 tickers) could exhaust the container's memory and fail with "Out of buffer" (500s, and
        # restarts). Bound how many loads run together and how much memory each may take.
        with _LOAD_SLOTS:
            conn = duckdb.connect(config={"memory_limit": _LOAD_MEMORY_LIMIT, "threads": _LOAD_THREADS})
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
    cache_info: dict | None = None,
    tail: bool | None = None,
    closed_only: bool = False,
    now_ts: int | None = None,
    sessions: str | None = None,
) -> list[dict]:
    """`sessions`: which trading sessions' bars to return: `regular` (default, 09:30-16:00 ET), `extended`, `all`, or a
    comma list of premarket / regular / afterhours / overnight (vinu_infra.sessions). Applied to the 1-minute bars BEFORE
    they are aggregated, so a 15m/1h/4h/1d bar is built only from the sessions asked for.
    `tail`: which `limit` bars to keep. True = the most recent ones, False = the oldest. Default (None):
    the most recent when the window has no explicit start (`from_ts` is None), the oldest when it does
    (forward pagination from `from_ts`). Before this, an open-ended request with a `limit` silently got the OLDEST
    bars of the whole history (v2 audit S1).
    `closed_only`: drop a trailing bar that is still forming (its bucket has not ended yet; v2 audit S2).

    `cache_info`, if passed, is filled in place with `{"hit": True,
    "age_seconds": float}` on an indicator-cache hit (item #19 finding #5)
    -- an out-param rather than changing this function's own return shape,
    since `list[dict]` is relied on by every other caller."""
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
    wanted = parse_sessions(sessions or os.environ.get("VINU_STOCK_DEFAULT_SESSION") or "regular")
    if not frozenset(TRADABLE_SESSIONS) <= wanted:
        mask &= session_mask(df["bar_ts"].to_numpy(), wanted)
    sub = df[mask].sort_values("bar_ts")
    if tail is None:
        tail = from_ts is None
    now_ts = int(time.time()) if now_ts is None else int(now_ts)

    def _keep(records: list[dict]) -> list[dict]:
        return records[-limit:] if tail else records[:limit]

    is_raw = interval.lower() == "1m"
    if is_raw:
        rows = sub.to_dict(orient="records")
        for rec in rows:
            rec["bar_ts"] = int(rec["bar_ts"])
            rec["adj_factor"] = float(rec.get("adj_factor", 1.0) or 1.0)
        if closed_only:
            rows = [r for r in rows if r["bar_ts"] + 60 <= now_ts]
        records = _keep(rows)
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
        aggregated = aggregate_bars(rows, interval)
        if closed_only:
            aggregated = [r for r in aggregated if bucket_end(r["bar_ts"], interval) <= now_ts]
        records = _keep(aggregated)

    if indicators:
        indicator_set = frozenset(indicators)
        cache = get_cache()
        # limit / tail / closed_only change which rows come back, so they belong in the key (v2 audit S3)
        ckey = f"{interval}#{limit}#{int(bool(tail))}#{int(closed_only)}#{spec_of(wanted)}"
        cached = cache.get(sym, ckey, from_ts, to_ts, indicator_set, adjusted)
        if cached is not None:
            records, age = cached
            if cache_info is not None:
                cache_info["hit"] = True
                cache_info["age_seconds"] = age
        else:
            records = apply_indicators(records, indicators)
            cache.set(sym, ckey, from_ts, to_ts, indicator_set, adjusted, records)
    return records
