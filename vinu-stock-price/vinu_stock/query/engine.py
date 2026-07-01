"""DuckDB query engine over Parquet archive + live."""

from __future__ import annotations

from pathlib import Path

import duckdb

from vinu_stock.query.aggregate import aggregate_bars
from vinu_stock.query.indicators import apply_adjusted_prices, apply_indicators
from vinu_stock.storage.paths import parquet_globs


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
    adjusted: bool = False,
) -> list[dict]:
    patterns = parquet_globs(data_root, symbol)
    if not patterns:
        return []

    sym = symbol.strip().upper()
    conn = duckdb.connect()
    try:
        placeholders = ", ".join(f"'{p}'" for p in patterns)
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
        sql += " ORDER BY bar_ts ASC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchdf()
        records = rows.to_dict(orient="records")
        for rec in records:
            rec["bar_ts"] = int(rec["bar_ts"])
            rec["adj_factor"] = float(rec.get("adj_factor", 1.0) or 1.0)
        records = aggregate_bars(records, interval)
        if adjusted:
            records = apply_adjusted_prices(records)
        if indicators:
            records = apply_indicators(records, indicators)
        return records
    finally:
        conn.close()
