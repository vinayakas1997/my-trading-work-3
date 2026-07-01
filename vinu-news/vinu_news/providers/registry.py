"""Ticker news provider registry."""

from __future__ import annotations

from vinu_news.config import VinuConfig, load_config
from vinu_news.providers.base import TickerNewsProvider
from vinu_news.providers.config.loader import load_ticker_news_providers
from vinu_news.providers.fmp import FmpTickerNewsProvider
from vinu_news.providers.yahoo import YahooTickerNewsProvider


class TickerNewsRegistry:
    def __init__(self, config: VinuConfig | None = None) -> None:
        self._config = config or load_config()
        self._providers = self._build_providers()

    def _build_providers(self) -> dict[str, TickerNewsProvider]:
        built: dict[str, TickerNewsProvider] = {
            "yahoo": YahooTickerNewsProvider(),
            "fmp": FmpTickerNewsProvider(self._config.fmp_api_key),
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
    ) -> list[dict]:
        raw: list[dict] = []
        seen_links: set[str] = set()
        for provider in self.list_enabled():
            try:
                items = provider.fetch_ticker_news(ticker, from_ts, to_ts)
            except Exception:
                continue
            for item in items:
                link = item.get("link", "")
                if link and link not in seen_links:
                    seen_links.add(link)
                    raw.append(item)
        return raw
