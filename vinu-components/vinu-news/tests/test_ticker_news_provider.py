"""Tests for ticker news providers (TASK-N02)."""

from vinu_news.providers.registry import TickerNewsRegistry


def test_registry_fetch_with_mock(monkeypatch):
    fixture = [
        {
            "headline": "Apple rises",
            "summary": "AAPL up",
            "link": "https://example.com/aapl-1",
            "pubDate": "Mon, 01 Jan 2024 12:00:00 GMT",
            "source": "YAHOO AAPL",
            "region": "US",
            "tier": 2,
            "category": "MARKETS",
        }
    ]

    error_count = 0

    class FakeYahoo:
        provider_id = "yahoo"

        def is_configured(self):
            return True

        def fetch_ticker_news(self, ticker, from_ts, to_ts):
            return fixture

    class FakeFailing:
        provider_id = "failing"

        def is_configured(self):
            return True

        def fetch_ticker_news(self, ticker, from_ts, to_ts):
            nonlocal error_count
            error_count += 1
            raise RuntimeError("provider down")

    registry = TickerNewsRegistry()
    monkeypatch.setattr(registry, "list_enabled", lambda: [FakeYahoo(), FakeFailing()])
    items, errors = registry.fetch_for_ticker("AAPL", 0, 9_999_999_999)
    assert len(items) == 1
    assert items[0]["headline"] == "Apple rises"
    assert errors == ["failing"]


def test_registry_fetch_all_fail(monkeypatch):
    class FakeFailing1:
        provider_id = "p1"

        def is_configured(self):
            return True

        def fetch_ticker_news(self, ticker, from_ts, to_ts):
            raise RuntimeError("p1 down")

    class FakeFailing2:
        provider_id = "p2"

        def is_configured(self):
            return True

        def fetch_ticker_news(self, ticker, from_ts, to_ts):
            raise RuntimeError("p2 down")

    registry = TickerNewsRegistry()
    monkeypatch.setattr(registry, "list_enabled", lambda: [FakeFailing1(), FakeFailing2()])
    items, errors = registry.fetch_for_ticker("AAPL", 0, 9_999_999_999)
    assert items == []
    assert errors == ["p1", "p2"]
