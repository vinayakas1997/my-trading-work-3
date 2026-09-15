from __future__ import annotations

import httpx

from vinu_screener.rankers.holdings_client import fetch_held_symbols


class _FakeResponse:
    def __init__(self, status_code: int, json_body=None):
        self.status_code = status_code
        self._json_body = json_body

    def json(self):
        return self._json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class TestFetchHeldSymbols:
    def test_empty_base_url_returns_empty_without_calling_httpx(self, monkeypatch) -> None:
        called = []
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: called.append(1))

        result = fetch_held_symbols("")

        assert result == frozenset()
        assert called == []

    def test_returns_uppercased_symbols(self, monkeypatch) -> None:
        body = [{"symbol": "aapl", "qty": "1"}, {"symbol": "MSFT", "qty": "2"}]
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, body))

        result = fetch_held_symbols("http://agent:8086")

        assert result == frozenset({"AAPL", "MSFT"})

    def test_non_200_returns_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(500))

        result = fetch_held_symbols("http://agent:8086")

        assert result == frozenset()

    def test_connection_error_returns_empty_and_does_not_raise(self, monkeypatch) -> None:
        def _raise(*a, **kw):
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx, "get", _raise)

        result = fetch_held_symbols("http://agent:8086")

        assert result == frozenset()

    def test_malformed_body_returns_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(httpx, "get", lambda *a, **kw: _FakeResponse(200, {"unexpected": "shape"}))

        result = fetch_held_symbols("http://agent:8086")

        assert result == frozenset()
