"""OHLCV interval aggregation from 1m bars."""

from __future__ import annotations

from datetime import datetime, timezone

INTERVAL_SECONDS: dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1wk": 604800,
}

# 1970-01-01 (epoch zero) was a Thursday, 3 days after the Monday that
# starts its own calendar week (1969-12-29 00:00 UTC). Plain epoch-aligned
# buckets (bar_ts // 604800 * 604800) would therefore start every "1wk"
# bucket on a Thursday, not the conventional Monday -- this offset
# re-aligns weekly buckets to real Monday-start calendar weeks.
_MONDAY_BEFORE_EPOCH_OFFSET = 3 * 86400

# "1mo"/"6mo" have no fixed real-world duration (months run 28-31 days),
# so bucketing them by a flat number of seconds (the old behavior: 2592000s
# = exactly 30 days, 15552000s = exactly 180 days) silently drifts away
# from real calendar month/half-year boundaries over time -- a bucket
# labeled "March" would eventually start containing late-February bars.
# These two are bucketed by actual calendar month instead (see
# _month_bucket_start/_six_month_bucket_start below), kept out of
# INTERVAL_SECONDS since they have no fixed duration.


def interval_to_seconds(interval: str) -> int:
    key = interval.strip().lower()
    if key not in INTERVAL_SECONDS:
        raise ValueError(f"Unsupported interval: {interval}")
    return INTERVAL_SECONDS[key]


def bucket_ts(bar_ts: int, interval_sec: int) -> int:
    return (bar_ts // interval_sec) * interval_sec


def _week_bucket_start(bar_ts: int) -> int:
    """Monday-00:00-UTC-aligned weekly bucket start."""
    shifted = bar_ts + _MONDAY_BEFORE_EPOCH_OFFSET
    return (shifted // 604800) * 604800 - _MONDAY_BEFORE_EPOCH_OFFSET


def _month_bucket_start(bar_ts: int) -> int:
    """Real calendar-month bucket start: the 1st of the bar's own UTC
    month, not a fixed 30-day window."""
    dt = datetime.fromtimestamp(bar_ts, tz=timezone.utc)
    return int(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp())


def _six_month_bucket_start(bar_ts: int) -> int:
    """Real calendar half-year bucket start, aligned to Jan 1 / Jul 1 of
    the bar's own UTC year, not a fixed 180-day window."""
    dt = datetime.fromtimestamp(bar_ts, tz=timezone.utc)
    start_month = 1 if dt.month <= 6 else 7
    return int(datetime(dt.year, start_month, 1, tzinfo=timezone.utc).timestamp())


def _bucket_fn_for(interval: str):
    key = interval.strip().lower()
    if key == "1wk":
        return _week_bucket_start
    if key == "1mo":
        return _month_bucket_start
    if key == "6mo":
        return _six_month_bucket_start
    interval_sec = interval_to_seconds(key)
    return lambda ts: bucket_ts(ts, interval_sec)


def aggregate_bars(rows: list[dict], interval: str) -> list[dict]:
    """Aggregate 1m bar dicts to higher timeframe."""
    if interval.lower() == "1m":
        return rows
    bucket_fn = _bucket_fn_for(interval)
    buckets: dict[int, dict] = {}
    for row in rows:
        b = bucket_fn(int(row["bar_ts"]))
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
