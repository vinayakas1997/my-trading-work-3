"""Ticker news provider registry."""

from __future__ import annotations

import logging

from vinu_news.config import VinuConfig, load_config
from vinu_news.providers.base import TickerNewsProvider
from vinu_news.providers.config.loader import load_ticker_news_providers
from vinu_news.providers.fmp import FmpTickerNewsProvider
from vinu_news.providers.alpaca import AlpacaTickerNewsProvider
from vinu_news.providers.yahoo import YahooTickerNewsProvider

LOG = logging.getLogger(__name__)


class TickerNewsRegistry:
    def __init__(self, config: VinuConfig | None = None) -> None:
        self._config = config or load_config()
        self._providers = self._build_providers()

    def _build_providers(self) -> dict[str, TickerNewsProvider]:
        built: dict[str, TickerNewsProvider] = {
            "yahoo": YahooTickerNewsProvider(),
            "fmp": FmpTickerNewsProvider(self._config.fmp_api_key),
            "alpaca": AlpacaTickerNewsProvider(
                self._config.alpaca_api_key,
                self._config.alpaca_api_secret,
            ),
        }
        return built

    def list_enabled(self) -> list[TickerNewsProvider]:
        configs = [c for c in load_ticker_news_providers() if c.enabled]
        out: list[TickerNewsProvider] = []
        for cfg in configs:
            provider = self._providers.get(cfg.id)
            if provider and provider.is_configured():
                out.append(provider)
        return out

    def fetch_for_ticker(
        self,
        ticker: str,
        from_ts: int,
        to_ts: int,
    ) -> tuple[list[dict], list[str]]:
        raw: list[dict] = []
        errors: list[str] = []
        seen_links: set[str] = set()
        for provider in self.list_enabled():
            try:
                items = provider.fetch_ticker_news(ticker, from_ts, to_ts)
            except Exception:
                errors.append(getattr(provider, "provider_id", "?"))
                LOG.warning(
                    "Provider %s failed for %s [%d, %d)",
                    getattr(provider, "provider_id", provider), ticker, from_ts, to_ts,
                    exc_info=True,
                )
                continue
            for item in items:
                link = item.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    raw.append(item)
        return raw, errors
