"""v2 audit S1-S3: `limit` keeps the most recent bars for an open-ended window, `closed_only` drops a still-forming
trailing bar, and the indicator cache key includes what changes the returned rows."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from vinu_stock.query import engine
from vinu_stock.query.aggregate import bucket_end
from vinu_stock.query.cache import get_cache

DAY = 86400
T0 = 1_700_006_400  # a UTC midnight


def _frame(days=10):
    rows = []
    for d in range(days):
        for m in range(2):
            ts = T0 + d * DAY + m * 60
            rows.append(dict(symbol="X", provider="p", bar_ts=ts, open=1.0 + d, high=1.0 + d, low=1.0 + d,
                             close=1.0 + d, volume=10.0, adj_factor=1.0))
    return pd.DataFrame(rows)


def _fetch(**kw):
    with patch.object(engine, "_load_symbol_frame", return_value=_frame()):
        return engine.fetch_candles(Path("."), "X", **kw)


def test_open_ended_limit_returns_the_most_recent_bars_not_the_oldest():
    out = _fetch(interval="1d", limit=2, now_ts=T0 + 20 * DAY)
    assert [r["close"] for r in out] == [9.0, 10.0]
    raw = _fetch(interval="1m", limit=3, now_ts=T0 + 20 * DAY)
    assert [r["bar_ts"] for r in raw] == [T0 + 8 * DAY + 60, T0 + 9 * DAY, T0 + 9 * DAY + 60]


def test_an_explicit_start_still_paginates_forward_from_it():
    out = _fetch(interval="1d", from_ts=T0 + 3 * DAY, limit=2, now_ts=T0 + 20 * DAY)
    assert [r["close"] for r in out] == [4.0, 5.0]
    assert [r["close"] for r in _fetch(interval="1d", from_ts=T0, limit=2, tail=True, now_ts=T0 + 20 * DAY)] == [9.0, 10.0]


def test_closed_only_drops_the_bucket_that_has_not_ended():
    now = T0 + 9 * DAY + 3600           # inside the last day
    assert _fetch(interval="1d", limit=50, now_ts=now)[-1]["close"] == 10.0
    closed = _fetch(interval="1d", limit=50, closed_only=True, now_ts=now)
    assert closed[-1]["close"] == 9.0 and len(closed) == 9
    assert len(_fetch(interval="1d", limit=50, closed_only=True, now_ts=T0 + 10 * DAY)) == 10   # day over: kept


def test_closed_only_on_raw_minutes_drops_a_minute_still_open():
    out = _fetch(interval="1m", limit=50, closed_only=True, now_ts=T0 + 9 * DAY + 90)
    assert out[-1]["bar_ts"] == T0 + 9 * DAY and len(out) == 19


def test_bucket_end_is_calendar_aware_for_months():
    jan1 = 1_704_067_200     # 2024-01-01
    assert bucket_end(jan1, "1mo") == jan1 + 31 * DAY
    assert bucket_end(jan1, "6mo") == jan1 + 182 * DAY     # Jan-Jun 2024 (leap year)
    assert bucket_end(jan1, "1h") == jan1 + 3600


def test_indicator_cache_does_not_serve_rows_for_a_different_limit():
    get_cache().invalidate()
    with patch.object(engine, "_load_symbol_frame", return_value=_frame()):
        a = engine.fetch_candles(Path("."), "X", interval="1d", limit=2, indicators=["sma_2"], now_ts=T0 + 20 * DAY)
        b = engine.fetch_candles(Path("."), "X", interval="1d", limit=5, indicators=["sma_2"], now_ts=T0 + 20 * DAY)
    assert len(a) == 2 and len(b) == 5
