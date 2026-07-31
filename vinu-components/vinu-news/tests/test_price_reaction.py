"""Tests for price reaction tagging (TASK-N03)."""

import requests

from vinu_news.analysis.post_enrichment.price_reaction import compute_price_changes
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
