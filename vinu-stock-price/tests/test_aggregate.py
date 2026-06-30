"""Aggregation tests."""

from __future__ import annotations

from vinu_stock.query.aggregate import aggregate_bars, bucket_ts


def test_bucket_ts() -> None:
    assert bucket_ts(305, 300) == 300


def test_aggregate_1m_to_5m() -> None:
    base = (1700000000 // 300) * 300  # align to 5m bucket
    rows = []
    for i in range(10):
        ts = base + i * 60
        rows.append(
            {
                "symbol": "AAPL",
                "provider": "test",
                "bar_ts": ts,
                "open": float(i),
                "high": float(i + 0.5),
                "low": float(i - 0.5),
                "close": float(i),
                "volume": 10.0,
            }
        )
    agg = aggregate_bars(rows, "5m")
    assert len(agg) == 2
    assert agg[0]["open"] == 0.0
    assert agg[0]["close"] == 4.0
    assert agg[0]["volume"] == 50.0
