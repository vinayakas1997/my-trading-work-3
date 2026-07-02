"""Storage backend protocol for vinu-news."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from vinu_news.analysis.storage.models import EnrichedArticle
from vinu_news.analysis.storage.persist import PersistResult
from vinu_news.analysis.storage.repository import NewsRepository

from vinu_news.settings.store import SettingsView


@runtime_checkable
class StorageBackend(Protocol):
    db_path: Path

    @property
    def repo(self) -> NewsRepository: ...

    def close(self) -> None: ...

    def __enter__(self) -> StorageBackend: ...

    def __exit__(self, *args: object) -> None: ...

    def get_settings(self) -> SettingsView: ...

    def patch_settings(
        self,
        *,
        mode: str | None = None,
        poll_interval_sec: int | None = None,
        llm_analysis_mode: str | None = None,
        llm_analysis_concurrency: int | None = None,
        active_tiers: list[int] | None = None,
    ) -> SettingsView: ...

    def get_watchlist(self) -> list[str]: ...

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]: ...

    def remove_watchlist_ticker(self, ticker: str) -> bool: ...

    def list_pending_ticker_fetch(self) -> list[str]: ...

    def clear_pending_ticker_fetch(self, tickers: list[str]) -> None: ...

    def clear_all_pending_ticker_fetch(self) -> None: ...

    def persist_leads(self, leads: list[EnrichedArticle]) -> PersistResult: ...

    def get_latest(
        self,
        limit: int = 20,
        date: str | None = None,
        provider: str | None = None,
        tiers: list[int] | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_articles_since(self, since_ts: int, limit: int = 100) -> list[dict[str, Any]]: ...

    def get_news_for_ticker(
        self,
        ticker: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def get_news_for_watchlist(
        self,
        tickers: list[str],
        start_ts: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def search_articles(self, query: str, limit: int = 50) -> list[dict[str, Any]]: ...

    def get_high_impact(
        self,
        since_ts: int,
        sentiment: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def get_active_threads(self, since_ts: int, limit: int = 200) -> list[dict[str, Any]]: ...

    def get_thread(self, thread_id: str) -> dict[str, Any] | None: ...

    def get_thread_articles(
        self, thread_id: str, limit: int = 50
    ) -> list[dict[str, Any]]: ...

    def get_thread_timeline(self, thread_id: str) -> list[dict[str, Any]]: ...

    def get_ticker_daily_stats(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]: ...

    def article_count(self) -> int: ...

    def health_info(self) -> dict[str, Any]: ...
