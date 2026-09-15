from __future__ import annotations

import httpx
import pytest

from vinu_agent.tools.screener_client import fetch_screener_top_tickers


class _FakeResponse:
    def __init__(self, status_code: int, json_body=None):
        self.status_code = status_code
        self._json_body = json_body

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class TestFetchScreenerTopTickers:
    def test_returns_symbols_in_rank_order(self, monkeypatch) -> None:
        body = {"top": [{"symbol": "AAPL", "final_score": 1.2}, {"symbol": "MSFT", "final_score": 0.9}]}
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, body))

        result = fetch_screener_top_tickers("http://screener:8095", "core_starter")

        assert result == ["AAPL", "MSFT"]

    def test_respects_limit(self, monkeypatch) -> None:
        body = {"top": [{"symbol": s} for s in ["A", "B", "C", "D"]]}
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, body))

        result = fetch_screener_top_tickers("http://screener:8095", "core_starter", limit=2)

        assert result == ["A", "B"]

    def test_404_ranker_not_yet_run_returns_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(404))

        result = fetch_screener_top_tickers("http://screener:8095", "core_starter")

        assert result == []

    def test_connection_error_returns_empty_and_does_not_raise(self, monkeypatch) -> None:
        def _raise(*a, **kw):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx, "get", _raise)

        result = fetch_screener_top_tickers("http://screener:8095", "core_starter")

        assert result == []

    def test_server_error_returns_empty_and_does_not_raise(self, monkeypatch) -> None:
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(500))

        result = fetch_screener_top_tickers("http://screener:8095", "core_starter")

        assert result == []

    def test_malformed_body_returns_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, {"unexpected": "shape"}))

        result = fetch_screener_top_tickers("http://screener:8095", "core_starter")

        assert result == []
