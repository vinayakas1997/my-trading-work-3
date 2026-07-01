"""OHLCV interval aggregation from 1m bars."""

from __future__ import annotations

INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def interval_to_seconds(interval: str) -> int:
    key = interval.strip().lower()
    if key not in INTERVAL_SECONDS:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_SECONDS[key]


def bucket_ts(bar_ts: int, interval_sec: int) -> int:
    return (bar_ts // interval_sec) * interval_sec


def aggregate_bars(rows: list[dict], interval: str) -> list[dict]:
    """Aggregate 1m bar dicts to higher timeframe."""
    if interval.lower() == "1m":
        return sorted(rows, key=lambda r: r["bar_ts"])
    interval_sec = interval_to_seconds(interval)
    buckets: dict[int, dict] = {}
    for row in sorted(rows, key=lambda r: r["bar_ts"]):
        b = bucket_ts(int(row["bar_ts"]), interval_sec)
        if b not in buckets:
            buckets[b] = {
                "symbol": row["symbol"],
                "provider": row.get("provider", ""),
                "bar_ts": b,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)),
                "adj_factor": float(row.get("adj_factor", 1.0) or 1.0),
            }
        else:
            agg = buckets[b]
            agg["high"] = max(agg["high"], float(row["high"]))
            agg["low"] = min(agg["low"], float(row["low"]))
            agg["close"] = float(row["close"])
            agg["volume"] += float(row.get("volume", 0))
            agg["adj_factor"] = float(row.get("adj_factor", 1.0) or 1.0)
    return [buckets[k] for k in sorted(buckets)]
