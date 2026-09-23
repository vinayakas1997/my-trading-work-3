"""Aggregation tests."""

from __future__ import annotations

from datetime import datetime, timezone

from vinu_stock.query.aggregate import aggregate_bars, bucket_ts, interval_to_seconds


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


def _bar(ts: int, price: float = 1.0) -> dict:
    return {
        "symbol": "AAPL", "provider": "test", "bar_ts": ts,
        "open": price, "high": price, "low": price, "close": price, "volume": 1.0,
    }


def test_interval_to_seconds_no_longer_covers_1mo_6mo() -> None:
    """Real bug found 2026-09-23: "1mo"/"6mo" used to be fixed-second
    entries (2592000s/15552000s -- a flat 30/180 days), which drifts from
    real calendar month boundaries over time. They're now bucketed by
    calendar month instead (see test_1mo_bucket_uses_real_calendar_month
    below), not by a fixed duration -- interval_to_seconds no longer
    accepts them at all."""
    import pytest
    with pytest.raises(ValueError):
        interval_to_seconds("1mo")
    with pytest.raises(ValueError):
        interval_to_seconds("6mo")


def test_1wk_bucket_is_monday_aligned_not_epoch_aligned() -> None:
    """Real bug found 2026-09-23: epoch zero (1970-01-01) was a Thursday,
    so plain epoch-aligned weekly buckets started on Thursdays, not the
    conventional Monday."""
    # 2026-09-23 is a Wednesday; its week should bucket to Monday 2026-09-21.
    wednesday = int(datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc).timestamp())
    monday = int(datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc).timestamp())
    rows = [_bar(wednesday)]
    agg = aggregate_bars(rows, "1wk")
    assert agg[0]["bar_ts"] == monday


def test_1mo_bucket_uses_real_calendar_month() -> None:
    """Real bug found 2026-09-23: the old fixed-2592000s (30-day) bucket
    would drift a bar taken near the end of a 31-day month into the wrong
    labeled month. A bar on Jan 31 must bucket to Jan 1, and a bar on
    Feb 1 (one day later) must bucket to a DIFFERENT, later bucket --
    the old fixed-duration bucket would have put both in the same one.
    """
    jan31 = int(datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc).timestamp())
    feb1 = int(datetime(2026, 2, 1, 0, 30, tzinfo=timezone.utc).timestamp())
    jan_start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    feb_start = int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp())

    agg = aggregate_bars([_bar(jan31)], "1mo")
    assert agg[0]["bar_ts"] == jan_start

    agg = aggregate_bars([_bar(feb1)], "1mo")
    assert agg[0]["bar_ts"] == feb_start


def test_6mo_bucket_aligns_to_jan_and_jul() -> None:
    june_bar = int(datetime(2026, 6, 30, 23, 0, tzinfo=timezone.utc).timestamp())
    july_bar = int(datetime(2026, 7, 1, 1, 0, tzinfo=timezone.utc).timestamp())
    h1_start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    h2_start = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp())

    agg = aggregate_bars([_bar(june_bar)], "6mo")
    assert agg[0]["bar_ts"] == h1_start

    agg = aggregate_bars([_bar(july_bar)], "6mo")
    assert agg[0]["bar_ts"] == h2_start
