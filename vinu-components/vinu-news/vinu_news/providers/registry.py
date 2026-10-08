"""Ticker news provider registry."""

from __future__ import annotations

import logging
from typing import Any

from vinu_news.config import VinuConfig, load_config
from vinu_news.providers.base import TickerNewsProvider
from vinu_news.providers.config.loader import load_ticker_news_providers
from vinu_news.providers.fmp import FmpTickerNewsProvider
from vinu_news.providers.alpaca import AlpacaTickerNewsProvider
from vinu_news.providers.yahoo import YahooTickerNewsProvider

LOG = logging.getLogger(__name__)


class TickerNewsRegistry:
    def __init__(self, config: VinuConfig | None = None, health: Any = None) -> None:
        self._config = config or load_config()
        self._providers = self._build_providers()
        self._health = health   # a SourceHealth: skips switched-off providers and records every outcome

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

    def _record(self, provider_id: str, *, ok: bool, error: str | None = None, articles: int | None = None) -> None:
        if self._health is None:
            return
        try:
            self._health.record(provider_id, ok=ok, error=error, kind="ticker_api", articles=articles)
        except Exception:  # noqa: BLE001 -- health bookkeeping must never stop a fetch
            LOG.warning("could not record health for provider %s", provider_id, exc_info=True)

    def list_enabled(self) -> list[TickerNewsProvider]:
        configs = [c for c in load_ticker_news_providers() if c.enabled]
        out: list[TickerNewsProvider] = []
        for cfg in configs:
            provider = self._providers.get(cfg.id)
            if not (provider and provider.is_configured()):
                continue
            if self._health is not None and not self._health.is_pollable(cfg.id):
                continue
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
            pid = getattr(provider, "provider_id", "?")
            try:
                items = provider.fetch_ticker_news(ticker, from_ts, to_ts)
                self._record(pid, ok=True, articles=len(items))
            except Exception as exc:
                self._record(pid, ok=False, error=f"{type(exc).__name__}: {exc}")
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
