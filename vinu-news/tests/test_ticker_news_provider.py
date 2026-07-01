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

    class FakeYahoo:
        provider_id = "yahoo"

        def is_configured(self):
            return True

        def fetch_ticker_news(self, ticker, from_ts, to_ts):
            return fixture

    registry = TickerNewsRegistry()
    monkeypatch.setattr(registry, "list_enabled", lambda: [FakeYahoo()])
    items = registry.fetch_for_ticker("AAPL", 0, 9_999_999_999)
    assert len(items) == 1
    assert items[0]["headline"] == "Apple rises"
