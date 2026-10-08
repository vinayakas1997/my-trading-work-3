"""item #19 finding #2 / item #21 pattern #1: vinu-news had the same
server-side-clamp gap as vinu-stock-price -- point-in-time safety existed
only because vinu-agent's tool code (news_tool.py) remembered to clamp
client-side. Tests the route function directly against a fake service
(the same `get_service` module-attribute-swap `create_app` itself uses),
not the full TestClient/app -- this repo's real NewsService construction
needs a configured data root unrelated to this fix.

Every FastAPI-Query-defaulted parameter is passed explicitly in every
call below -- calling a route function directly (bypassing FastAPI's own
request handling) means an omitted parameter gets the literal `Query(...)`
sentinel object as its value, not the resolved default, so relying on
Python's own default-argument mechanism here would silently test the
wrong thing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import Response

from vinu_news.server import routes_read


def _fake_service(rows: list[dict] | None = None) -> MagicMock:
    service = MagicMock()
    service.get_ticker_news.return_value = rows if rows is not None else []
    return service


class TestTickerNewsAsOfClamp:
    def test_no_as_of_passes_explicit_to_through_unchanged(self) -> None:
        service = _fake_service()
        response = Response()
        routes_read.get_service = lambda: service
        routes_read.ticker_news(
            "AAPL", response, days=7, limit=50, reaction=False, from_=None, to=5000, as_of=None,
        )
        service.get_ticker_news.assert_called_once_with(
            "AAPL", from_ts=None, to_ts=5000, limit=50, include_reaction=False,
        )
        assert "X-Clamped-To-As-Of" not in response.headers

    def test_to_beyond_as_of_is_clamped(self) -> None:
        service = _fake_service()
        response = Response()
        routes_read.get_service = lambda: service
        routes_read.ticker_news(
            "AAPL", response, days=7, limit=50, reaction=False, from_=None, to=5000, as_of=3000,
        )
        service.get_ticker_news.assert_called_once_with(
            "AAPL", from_ts=None, to_ts=3000, limit=50, include_reaction=False,
        )
        assert response.headers.get("X-Clamped-To-As-Of") == "true"

    def test_to_within_as_of_is_not_clamped(self) -> None:
        service = _fake_service()
        response = Response()
        routes_read.get_service = lambda: service
        routes_read.ticker_news(
            "AAPL", response, days=7, limit=50, reaction=False, from_=None, to=1000, as_of=3000,
        )
        service.get_ticker_news.assert_called_once_with(
            "AAPL", from_ts=None, to_ts=1000, limit=50, include_reaction=False,
        )
        assert "X-Clamped-To-As-Of" not in response.headers

    def test_no_explicit_to_defaults_to_as_of_when_set(self) -> None:
        """The unbounded-query gap this closes: a caller under replay that
        doesn't pass an explicit `to` at all must still never see data
        past as_of -- not fall through to the plain days-relative-to-now
        branch."""
        service = _fake_service()
        response = Response()
        routes_read.get_service = lambda: service
        routes_read.ticker_news(
            "AAPL", response, days=7, limit=50, reaction=False, from_=None, to=None, as_of=3000,
        )
        service.get_ticker_news.assert_called_once_with(
            "AAPL", from_ts=None, to_ts=3000, limit=50, include_reaction=False,
        )
        assert response.headers.get("X-Clamped-To-As-Of") == "true"

    def test_no_as_of_and_no_explicit_range_uses_the_plain_days_path(self) -> None:
        service = _fake_service()
        response = Response()
        routes_read.get_service = lambda: service
        routes_read.ticker_news(
            "AAPL", response, days=7, limit=50, reaction=False, from_=None, to=None, as_of=None,
        )
        service.get_ticker_news.assert_called_once_with("AAPL", days=7, limit=50, include_reaction=False)
        assert "X-Clamped-To-As-Of" not in response.headers
