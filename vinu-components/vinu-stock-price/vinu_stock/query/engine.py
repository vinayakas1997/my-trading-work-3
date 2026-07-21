"""DuckDB query engine over Parquet archive + live."""

from __future__ import annotations

from pathlib import Path

import duckdb

from vinu_stock.query.aggregate import aggregate_bars, interval_to_seconds
from vinu_stock.query.cache import get_cache
from vinu_stock.query.indicators import apply_adjusted_prices, apply_indicators
from vinu_stock.storage.paths import parquet_globs_by_range


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
    patterns = parquet_globs_by_range(data_root, symbol, from_ts=from_ts, to_ts=to_ts)
    if not patterns:
        return []

    sym = symbol.strip().upper()
    own_conn = False
    if connection is not None:
        conn = connection.cursor()
    else:
        conn = duckdb.connect()
        own_conn = True

    try:
        placeholders = ", ".join(f"'{p}'" for p in patterns)
        is_raw = interval.lower() == "1m"

        if is_raw:
            # No aggregation needed — fetch raw 1m bars. Dedup via QUALIFY.
            sql = f"""
                SELECT symbol, provider, bar_ts, open, high, low, close, volume,
                       COALESCE(adj_factor, 1.0) AS adj_factor
                FROM read_parquet([{placeholders}], union_by_name=true)
                WHERE symbol = ?
            """
            params: list = [sym]
            if from_ts is not None:
                sql += " AND bar_ts >= ?"
                params.append(from_ts)
            if to_ts is not None:
                sql += " AND bar_ts <= ?"
                params.append(to_ts)
            if provider:
                sql += " AND provider = ?"
                params.append(provider.strip().lower())
            sql += """
                QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol, provider, bar_ts ORDER BY bar_ts DESC) = 1
            """
            sql += " ORDER BY bar_ts ASC"

            rows = conn.execute(sql, params).fetchdf()
            records = rows.to_dict(orient="records")
            for rec in records:
                rec["bar_ts"] = int(rec["bar_ts"])
                rec["adj_factor"] = float(rec.get("adj_factor", 1.0) or 1.0)
            records = records[:limit]
            if adjusted:
                records = apply_adjusted_prices(records)
        else:
            # Push aggregation + adjusted prices + LIMIT into DuckDB SQL.
            # First pass: dedup raw 1m rows via CTE, then GROUP BY bucket_ts.
            interval_sec = interval_to_seconds(interval)
            raw_from = from_ts
            raw_to = to_ts

            dedup_sql = f"""
                WITH raw AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY symbol, provider, bar_ts ORDER BY bar_ts DESC) AS rn
                    FROM read_parquet([{placeholders}], union_by_name=true)
                    WHERE symbol = ?
            """
            params = [sym]
            if raw_from is not None:
                dedup_sql += " AND bar_ts >= ?"
                params.append(raw_from)
            if raw_to is not None:
                dedup_sql += " AND bar_ts <= ?"
                params.append(raw_to)
            if provider:
                dedup_sql += " AND provider = ?"
                params.append(provider.strip().lower())

            if adjusted:
                ohlc_cols = """
                       FIRST(open * COALESCE(adj_factor, 1.0) ORDER BY bar_ts ASC) AS open,
                       MAX(high * COALESCE(adj_factor, 1.0)) AS high,
                       MIN(low * COALESCE(adj_factor, 1.0)) AS low,
                       LAST(close * COALESCE(adj_factor, 1.0) ORDER BY bar_ts ASC) AS close"""
            else:
                ohlc_cols = """
                       FIRST(open ORDER BY bar_ts ASC) AS open,
                       MAX(high) AS high,
                       MIN(low) AS low,
                       LAST(close ORDER BY bar_ts ASC) AS close"""

            dedup_sql += f"""
                )
                SELECT symbol, provider,
                       (bar_ts // {interval_sec}) * {interval_sec} AS bar_ts,
                       {ohlc_cols},
                       SUM(volume) AS volume,
                       LAST(COALESCE(adj_factor, 1.0) ORDER BY bar_ts ASC) AS adj_factor
                FROM raw
                WHERE rn = 1
                GROUP BY symbol, provider, (bar_ts // {interval_sec}) * {interval_sec}
                ORDER BY bar_ts ASC
                LIMIT {limit}
            """

            rows = conn.execute(dedup_sql, params).fetchdf()
            records = rows.to_dict(orient="records")
            for rec in records:
                rec["bar_ts"] = int(rec["bar_ts"])
                rec["adj_factor"] = float(rec.get("adj_factor", 1.0) or 1.0)

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
    finally:
        conn.close()

