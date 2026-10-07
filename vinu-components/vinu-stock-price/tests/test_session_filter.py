"""Candles honour a `session`: default regular hours; extended / overnight / all on request; aggregation uses only the
sessions asked for. Plus the overnight bars the Alpaca provider adds."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from vinu_infra.sessions import NY, OVERNIGHT, REGULAR, session_of
from vinu_stock.config import VinuStockConfig
from vinu_stock.providers.alpaca import AlpacaProvider
from vinu_stock.query import engine


def _ts(d, h, m=0):
    return int(datetime(2026, 10, d, h, m, tzinfo=NY).timestamp())


def _write(tmp_path, stamps):
    d = tmp_path / "prices" / "1m" / "X" / "live"
    d.mkdir(parents=True)
    rows = [dict(symbol="X", provider="alpaca", bar_ts=t, open=100.0, high=101.0, low=99.0, close=100.0 + i, volume=10.0,
                 adj_factor=1.0) for i, t in enumerate(stamps)]
    pd.DataFrame(rows).to_parquet(d / "X.parquet")
    engine.invalidate_symbol_cache()


# Monday 2026-10-05 and Tuesday 10-06: overnight (Mon 02:00), premarket 05:00, regular 10:00 and 15:00, afterhours 17:00,
# overnight 21:00 (Mon evening), and Tuesday 10:00
STAMPS = [_ts(5, 2), _ts(5, 5), _ts(5, 10), _ts(5, 15), _ts(5, 17), _ts(5, 21), _ts(6, 10)]


def test_default_is_regular_hours_only(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STOCK_DEFAULT_SESSION", raising=False)
    _write(tmp_path, STAMPS)
    got = engine.fetch_candles(tmp_path, "X", interval="1m")
    assert [session_of(r["bar_ts"]) for r in got] == [REGULAR, REGULAR, REGULAR]


def test_the_operator_setting_changes_the_default(tmp_path, monkeypatch):
    _write(tmp_path, STAMPS)
    monkeypatch.setenv("VINU_STOCK_DEFAULT_SESSION", "overnight")
    assert [session_of(r["bar_ts"]) for r in engine.fetch_candles(tmp_path, "X", interval="1m")] == [OVERNIGHT, OVERNIGHT]
    assert len(engine.fetch_candles(tmp_path, "X", interval="1m", sessions="all")) == len(STAMPS)     # a request still wins


def test_extended_all_and_named_sessions(tmp_path):
    _write(tmp_path, STAMPS)
    sessions = lambda spec: [session_of(r["bar_ts"]) for r in engine.fetch_candles(tmp_path, "X", interval="1m", sessions=spec)]
    assert REGULAR not in sessions("extended") and len(sessions("extended")) == 4
    assert len(sessions("all")) == len(STAMPS)
    assert sessions("overnight") == [OVERNIGHT, OVERNIGHT]
    assert sessions("regular,overnight") == [OVERNIGHT, REGULAR, REGULAR, OVERNIGHT, REGULAR]


def test_a_daily_bar_is_built_only_from_the_sessions_asked_for(tmp_path):
    _write(tmp_path, STAMPS)
    regular = engine.fetch_candles(tmp_path, "X", interval="1d", from_ts=0, sessions="regular")
    everything = engine.fetch_candles(tmp_path, "X", interval="1d", from_ts=0, sessions="all")
    assert sum(r["volume"] for r in regular) == 30.0 and sum(r["volume"] for r in everything) == 70.0


def test_indicator_cache_does_not_mix_sessions(tmp_path):
    _write(tmp_path, STAMPS)
    a = engine.fetch_candles(tmp_path, "X", interval="1m", indicators=["sma_2"], sessions="regular")
    b = engine.fetch_candles(tmp_path, "X", interval="1m", indicators=["sma_2"], sessions="all")
    assert len(a) == 3 and len(b) == len(STAMPS)


# ---- the provider adds overnight bars from the overnight feed ------------------------------------------------------------

def _config():
    return VinuStockConfig(
        data_root="/tmp/d", meta_db_path="/tmp/d/x.db", default_poll_interval_sec=60, host="h", port=1, default_provider="alpaca",
        polygon_api_key="", alpaca_api_key="k", alpaca_api_secret="s", alpaca_data_base_url="https://data.alpaca.markets",
        shared_watchlist_path=None, shared_root=None, finnhub_api_key="", events_macro_enabled=False, events_refresh_hours=24.0)


class _Resp:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p


def _iso(t):
    return datetime.fromtimestamp(t, tz=NY).astimezone(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row(t):
    return {"t": _iso(t), "o": 1, "h": 1, "l": 1, "c": 1, "v": 5, "n": 1}


def test_overnight_bars_from_the_overnight_feed_are_merged_and_only_overnight_ones(monkeypatch):
    monkeypatch.delenv("VINU_STOCK_OVERNIGHT_FEED", raising=False)
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append(params["feed"])
        if params["feed"] == "iex":
            return _Resp({"bars": {"X": [_row(_ts(5, 10))]}})
        # the overnight feed returns an overnight bar AND a stray regular-session one that must be ignored
        return _Resp({"bars": {"X": [_row(_ts(5, 2)), _row(_ts(5, 11))]}})

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get)
    res = AlpacaProvider(_config()).fetch_bars_multi(["X"], 0, 10**10)["X"]
    assert calls == ["iex", "boats"] and res.success
    assert [session_of(b.bar_ts) for b in res.bars] == [OVERNIGHT, REGULAR]
    single = AlpacaProvider(_config()).fetch_bars("X", 0, 10**10)
    assert [session_of(b.bar_ts) for b in single.bars] == [OVERNIGHT, REGULAR]


def test_a_failing_overnight_feed_keeps_the_regular_bars(monkeypatch):
    monkeypatch.delenv("VINU_STOCK_OVERNIGHT_FEED", raising=False)

    def fake_get(url, params, headers, timeout):
        if params["feed"] == "boats":
            raise RuntimeError("feed unavailable")
        return _Resp({"bars": {"X": [_row(_ts(5, 10))]}})

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get)
    res = AlpacaProvider(_config()).fetch_bars_multi(["X"], 0, 10**10)["X"]
    assert res.success and len(res.bars) == 1


def test_the_overnight_feed_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("VINU_STOCK_OVERNIGHT_FEED", "")
    seen = []
    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry",
                        lambda url, params, headers, timeout: (seen.append(params["feed"]), _Resp({"bars": {"X": []}}))[1])
    AlpacaProvider(_config()).fetch_bars_multi(["X"], 0, 10**10)
    assert seen == ["iex"]


def test_the_overnight_request_stops_short_of_the_last_fifteen_minutes(monkeypatch):
    """The plan answers 403 to an overnight-feed window that reaches into the last 15 minutes; the live ingest asks up to now."""
    import datetime as dt

    monkeypatch.delenv("VINU_STOCK_OVERNIGHT_FEED", raising=False)
    seen = {}

    def fake_get(url, params, headers, timeout):
        if params["feed"] == "boats":
            seen["end"] = params["end"]
        return _Resp({"bars": {"X": []}})

    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry", fake_get)
    now = dt.datetime.now(dt.timezone.utc)
    AlpacaProvider(_config()).fetch_bars_multi(["X"], int((now - dt.timedelta(hours=2)).timestamp()), int(now.timestamp()))
    end = dt.datetime.fromisoformat(seen["end"].replace("Z", "+00:00"))
    assert end <= now - dt.timedelta(minutes=15)


def test_a_window_entirely_inside_the_delay_makes_no_overnight_call(monkeypatch):
    import datetime as dt

    monkeypatch.delenv("VINU_STOCK_OVERNIGHT_FEED", raising=False)
    feeds = []
    monkeypatch.setattr("vinu_stock.providers.alpaca.http_get_with_retry",
                        lambda url, params, headers, timeout: (feeds.append(params["feed"]), _Resp({"bars": {"X": []}}))[1])
    now = dt.datetime.now(dt.timezone.utc)
    AlpacaProvider(_config()).fetch_bars_multi(["X"], int((now - dt.timedelta(minutes=5)).timestamp()), int(now.timestamp()))
    assert feeds == ["iex"]
