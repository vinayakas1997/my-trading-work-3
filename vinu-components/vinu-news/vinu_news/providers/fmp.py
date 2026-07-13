"""FMP ticker news provider stub (TASK-N02)."""

from __future__ import annotations

from vinu_news.providers.base import NotConfiguredError


class FmpTickerNewsProvider:
    provider_id = "fmp"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.strip()

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def fetch_ticker_news(
        self,
        ticker: str,
        from_ts: int,
        to_ts: int,
    ) -> list[dict]:
        if not self.is_configured():
            raise NotConfiguredError("FMP_API_KEY not set")
        # Future: implement FMP stock_news endpoint
        return []
