"""Tests for AlpacaTickerNewsProvider's failure-path logging (finding #29):
`fetch_ticker_news`'s `except requests.RequestException` handler used to
reference `resp` before it was ever assigned in that try block (the
request call itself is what raised), producing a `NameError` that
destroyed the real error message. This is caught one level up by
`registry.py` so it wasn't fatal, but it made every connection failure's
log line useless for diagnosis."""

from __future__ import annotations

import logging

import requests

from vinu_news.providers.alpaca import AlpacaTickerNewsProvider


def test_connection_error_logs_the_real_error_without_raising_nameerror(monkeypatch, caplog):
    provider = AlpacaTickerNewsProvider("key", "secret")

    def fake_request(method, url, **kwargs):
        raise requests.ConnectionError("Connection refused")

    monkeypatch.setattr("vinu_news.providers.alpaca.net.request", fake_request)
    monkeypatch.setattr("vinu_news.providers.alpaca._RATE_LIMITER.wait", lambda: None)

    with caplog.at_level(logging.WARNING):
        articles = provider.fetch_ticker_news("AAPL", 0, 1_700_000_000)

    assert articles == []
    # The real exception message must reach the log -- not a NameError
    # from referencing an unassigned `resp`.
    assert any("Connection refused" in r.getMessage() for r in caplog.records)
    assert not any("NameError" in r.getMessage() for r in caplog.records)


def test_http_error_with_response_logs_status_and_body(monkeypatch, caplog):
    provider = AlpacaTickerNewsProvider("key", "secret")

    fake_resp = requests.Response()
    fake_resp.status_code = 429
    fake_resp._content = b"rate limited"

    def fake_request(method, url, **kwargs):
        raise requests.HTTPError("429 Client Error", response=fake_resp)

    monkeypatch.setattr("vinu_news.providers.alpaca.net.request", fake_request)
    monkeypatch.setattr("vinu_news.providers.alpaca._RATE_LIMITER.wait", lambda: None)

    with caplog.at_level(logging.WARNING):
        articles = provider.fetch_ticker_news("AAPL", 0, 1_700_000_000)

    assert articles == []
    assert any("429" in r.getMessage() and "rate limited" in r.getMessage() for r in caplog.records)
