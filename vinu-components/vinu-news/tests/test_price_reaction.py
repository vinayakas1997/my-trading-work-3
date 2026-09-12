"""Tests for price reaction tagging (TASK-N03)."""

import sqlite3

import requests

from vinu_news.analysis.post_enrichment.price_reaction import (
    compute_price_changes,
    enrich_article_with_reaction,
    enrich_articles_with_reaction,
)
from vinu_news.integrations.stock_price import StockPriceClient


def test_compute_price_changes():
    base_ts = 1_700_000_000
    candles = [
        {"bar_ts": base_ts, "close": 100.0},
        {"bar_ts": base_ts + 3600, "close": 105.0},
        {"bar_ts": base_ts + 86400, "close": 110.0},
    ]
    ch_1h, ch_1d = compute_price_changes(candles, base_ts)
    assert ch_1h == 5.0
    assert ch_1d == 10.0


def _make_http_error(status_code: int) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status_code
    return requests.HTTPError(f"HTTP {status_code}", response=resp)


def test_get_candles_404_returns_empty(monkeypatch):
    seen = {}

    def fake_request(method, url, params=None, timeout=None):
        seen["url"] = url
        raise _make_http_error(404)

    monkeypatch.setattr(
        "vinu_news.integrations.stock_price.http_request", fake_request
    )
    client = StockPriceClient("http://stock-api:8081")
    assert client.get_candles("SPDR") == []
    assert seen["url"].endswith("/stock/candles/SPDR")


def test_get_candles_other_errors_raise(monkeypatch):
    def fake_request(method, url, params=None, timeout=None):
        raise _make_http_error(500)

    monkeypatch.setattr(
        "vinu_news.integrations.stock_price.http_request", fake_request
    )
    client = StockPriceClient("http://stock-api:8081")
    try:
        client.get_candles("AAPL")
    except requests.HTTPError:
        pass
    else:
        raise AssertionError("expected HTTPError to propagate for non-404")


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE article_price_reaction (
            article_id TEXT PRIMARY KEY,
            price_change_1h REAL,
            price_change_1d REAL,
            computed_at INTEGER NOT NULL
        )
        """
    )
    return conn


class _FakeClient:
    """Records get_candles calls and serves fixed candles per ticker."""

    def __init__(self, candles_by_ticker):
        self._candles_by_ticker = candles_by_ticker
        self.calls = []

    def get_candles(self, symbol, *, from_ts=None, to_ts=None, limit=500):
        self.calls.append((symbol, from_ts, to_ts, limit))
        return self._candles_by_ticker.get(symbol, [])


def _article(article_id, ticker, sort_ts):
    import json

    return {
        "id": article_id,
        "tickers": json.dumps([ticker]),
        "sort_ts": sort_ts,
    }


def test_enrich_articles_batches_same_ticker_same_day_into_one_fetch():
    base_ts = 1_700_000_000  # a fixed UTC instant
    candles = [
        {"bar_ts": base_ts - 3600, "close": 100.0},
        {"bar_ts": base_ts, "close": 100.0},
        {"bar_ts": base_ts + 3600, "close": 105.0},
        {"bar_ts": base_ts + 7200, "close": 106.0},
        {"bar_ts": base_ts + 86400, "close": 110.0},
        {"bar_ts": base_ts + 90000, "close": 111.0},
    ]
    client = _FakeClient({"AAPL": candles})
    conn = _make_conn()

    # Two AAPL articles an hour apart, same UTC day -> should share one fetch.
    articles = [
        _article("a1", "AAPL", base_ts),
        _article("a2", "AAPL", base_ts + 3600),
    ]

    results = enrich_articles_with_reaction(conn, articles, client)

    assert len(client.calls) == 1  # deduped into a single get_candles call
    assert results[0]["price_change_1h"] == 5.0
    assert results[0]["price_change_1d"] == 10.0
    # a2's base_ts is base_ts+3600, whose closest close-at-or-after itself is 105.0
    ch_1h_a2, ch_1d_a2 = compute_price_changes(candles, base_ts + 3600)
    assert results[1]["price_change_1h"] == ch_1h_a2
    assert results[1]["price_change_1d"] == ch_1d_a2

    # Matches what per-article enrichment would have produced.
    conn2 = _make_conn()
    expected0 = enrich_article_with_reaction(conn2, articles[0], client)
    expected1 = enrich_article_with_reaction(conn2, articles[1], client)
    assert results[0]["price_change_1h"] == expected0["price_change_1h"]
    assert results[0]["price_change_1d"] == expected0["price_change_1d"]
    assert results[1]["price_change_1h"] == expected1["price_change_1h"]
    assert results[1]["price_change_1d"] == expected1["price_change_1d"]


def test_enrich_articles_different_tickers_and_days_fetch_separately():
    base_ts = 1_700_000_000
    next_day_ts = base_ts + 86400 * 3  # clearly a different UTC day
    candles_aapl = [
        {"bar_ts": base_ts, "close": 100.0},
        {"bar_ts": base_ts + 3600, "close": 101.0},
    ]
    candles_msft = [
        {"bar_ts": base_ts, "close": 200.0},
        {"bar_ts": base_ts + 3600, "close": 202.0},
    ]
    client = _FakeClient({"AAPL": candles_aapl, "MSFT": candles_msft})
    conn = _make_conn()

    articles = [
        _article("a1", "AAPL", base_ts),
        _article("a2", "MSFT", base_ts),  # different ticker, same day
        _article("a3", "AAPL", next_day_ts),  # same ticker, different day
    ]

    results = enrich_articles_with_reaction(conn, articles, client)

    assert len(client.calls) == 3  # no cross-group sharing
    assert results[0]["price_change_1h"] == 1.0
    assert results[1]["price_change_1h"] == 1.0


def test_enrich_articles_uses_cache_and_skips_network():
    conn = _make_conn()
    conn.execute(
        "INSERT INTO article_price_reaction VALUES (?, ?, ?, ?)",
        ("a1", 1.5, 2.5, 1_700_000_000),
    )
    conn.commit()
    client = _FakeClient({})

    results = enrich_articles_with_reaction(
        conn, [_article("a1", "AAPL", 1_700_000_000)], client
    )

    assert client.calls == []
    assert results[0]["price_change_1h"] == 1.5
    assert results[0]["price_change_1d"] == 2.5


def test_enrich_articles_single_member_group_matches_original_params():
    base_ts = 1_700_000_000
    client = _FakeClient({"AAPL": []})
    conn = _make_conn()

    enrich_articles_with_reaction(conn, [_article("a1", "AAPL", base_ts)], client)

    assert len(client.calls) == 1
    symbol, from_ts, to_ts, limit = client.calls[0]
    assert symbol == "AAPL"
    assert from_ts == base_ts
    assert to_ts == base_ts + 86400 + 3600
    assert limit == 2000
