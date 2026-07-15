from __future__ import annotations

from unittest.mock import MagicMock

from vinu_stock.providers.registry import (
    FALLBACK_CHAINS,
    VALID_SOURCES,
    ProviderRegistry,
    resolve_loader,
)


class TestFallbackChains:
    def test_us_equity_chain(self):
        assert "alpaca" in FALLBACK_CHAINS["us_equity"]
        assert "polygon" in FALLBACK_CHAINS["us_equity"]
        assert "yahoo" in FALLBACK_CHAINS["us_equity"]

    def test_known_markets(self):
        for market in ("us_equity", "crypto", "a_share"):
            assert market in FALLBACK_CHAINS


class TestValidSources:
    def test_contains_expected_sources(self):
        assert "alpaca" in VALID_SOURCES
        assert "polygon" in VALID_SOURCES
        assert "yahoo" in VALID_SOURCES
        assert "local" in VALID_SOURCES

    def test_accepts_valid_source(self):
        assert set(FALLBACK_CHAINS["us_equity"]).issubset(VALID_SOURCES)


class TestResolveLoader:
    def test_returns_configured_provider(self):
        registry = ProviderRegistry()
        mock_alpaca = MagicMock()
        mock_alpaca.provider_id = "alpaca"
        mock_alpaca.is_configured.return_value = True
        registry._providers["alpaca"] = mock_alpaca

        provider = resolve_loader("us_equity", registry)
        assert provider is not None
        assert provider.provider_id == "alpaca"

    def test_returns_none_when_unconfigured(self):
        registry = ProviderRegistry()
        for p in registry._providers.values():
            if hasattr(p, "is_configured"):
                mock = MagicMock()
                mock.is_configured.return_value = False
                registry._providers[p.provider_id] = mock

        provider = resolve_loader("us_equity", registry)
        assert provider is None

    def test_unknown_market_falls_back_to_us_equity(self):
        registry = ProviderRegistry()
        mock_yahoo = MagicMock()
        mock_yahoo.is_configured.return_value = True
        registry._providers["yahoo"] = mock_yahoo

        provider = resolve_loader("unknown_market", registry)
        assert provider is not None


class TestFetchForMarket:
    def test_falls_through_chain(self):
        registry = ProviderRegistry()
        mock_alpaca = MagicMock()
        mock_alpaca.provider_id = "alpaca"
        mock_alpaca.is_configured.return_value = True
        mock_alpaca.fetch_bars.return_value = type(
            "R", (), {"success": False, "bars": [], "error": "fail"}
        )()

        mock_yahoo = MagicMock()
        mock_yahoo.provider_id = "yahoo"
        mock_yahoo.is_configured.return_value = True
        mock_yahoo.fetch_bars.return_value = type(
            "R",
            (),
            {
                "success": True,
                "bars": [type("B", (), {"symbol": "AAPL", "close": 150.0})()],
                "error": "",
            },
        )()

        registry._providers["alpaca"] = mock_alpaca
        registry._providers["yahoo"] = mock_yahoo

        result = registry.fetch_for_market("us_equity", "AAPL", 0, 100)
        assert result.success is True

    def test_all_providers_fail(self):
        registry = ProviderRegistry()
        mock_alpaca = MagicMock()
        mock_alpaca.provider_id = "alpaca"
        mock_alpaca.is_configured.return_value = True
        mock_alpaca.fetch_bars.return_value = type(
            "R", (), {"success": False, "bars": [], "error": "fail"}
        )()
        registry._providers["alpaca"] = mock_alpaca

        result = registry.fetch_for_market("us_equity", "AAPL", 0, 100)
        assert result.success is False
        assert "alpaca" in result.error
