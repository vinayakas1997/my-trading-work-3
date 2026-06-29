"""SQLite storage backend wrapping NewsRepository."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vinu_news.analysis.storage.models import EnrichedArticle
from vinu_news.analysis.storage.persist import PersistResult, persist_leads
from vinu_news.analysis.storage.repository import NewsRepository

from vinu_news.config import settings_env_defaults
from vinu_news.settings.store import SettingsStore, SettingsView
from vinu_news.watchlist.store import WatchlistStore

_SETTINGS_SCHEMA = (
    Path(__file__).resolve().parent.parent / "settings" / "schema.sql"
)
_WATCHLIST_SCHEMA = (
    Path(__file__).resolve().parent.parent / "watchlist" / "schema.sql"
)


class SqliteBackend:
    """SQLite implementation with vinu settings and watchlist tables."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._repo = NewsRepository(db_path)
        self.db_path = self._repo.db_path
        self._settings = SettingsStore(self._repo.conn)
        self._watchlist = WatchlistStore(self._repo.conn)
        self._init_vinu_schema()

    @property
    def repo(self) -> NewsRepository:
        return self._repo

    def _init_vinu_schema(self) -> None:
        env_defaults = settings_env_defaults()
        self._settings.init_schema(
            _SETTINGS_SCHEMA.read_text(encoding="utf-8"),
            env_defaults=env_defaults,
        )
        self._watchlist.init_schema(_WATCHLIST_SCHEMA.read_text(encoding="utf-8"))
        self._repo.conn.commit()

    def close(self) -> None:
        self._repo.close()

    def __enter__(self) -> SqliteBackend:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_settings(self) -> SettingsView:
        return self._settings.get_all()

    def patch_settings(
        self,
        *,
        mode: str | None = None,
        poll_interval_sec: int | None = None,
    ) -> SettingsView:
        return self._settings.patch(mode=mode, poll_interval_sec=poll_interval_sec)

    def get_watchlist(self) -> list[str]:
        return self._watchlist.list_tickers()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        return self._watchlist.add_tickers(tickers)

    def remove_watchlist_ticker(self, ticker: str) -> bool:
        return self._watchlist.remove_ticker(ticker)

    def persist_leads(self, leads: list[EnrichedArticle]) -> PersistResult:
        return persist_leads(self._repo, leads)

    def get_latest(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._repo.conn.execute(
            """
            SELECT * FROM articles
            WHERE is_lead = 1
            ORDER BY sort_ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_articles_since(self, since_ts: int, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._repo.conn.execute(
            """
            SELECT * FROM articles
            WHERE sort_ts >= ? AND is_lead = 1
            ORDER BY sort_ts DESC
            LIMIT ?
            """,
            (since_ts, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_news_for_ticker(
        self,
        ticker: str,
        start_ts: int | None = None,
        end_ts: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._repo.get_news_for_ticker(ticker, start_ts, end_ts, limit)

    def get_news_for_watchlist(
        self,
        tickers: list[str],
        start_ts: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not tickers:
            return []
        per_ticker = max(1, limit // len(tickers))
        seen: set[str] = set()
        combined: list[dict[str, Any]] = []
        for symbol in tickers:
            rows = self.get_news_for_ticker(symbol, start_ts, None, per_ticker)
            for row in rows:
                article_id = row["id"]
                if article_id in seen:
                    continue
                seen.add(article_id)
                combined.append(row)
        combined.sort(key=lambda r: r["sort_ts"], reverse=True)
        return combined[:limit]

    def search_articles(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._repo.search_articles(query, limit)

    def get_high_impact(
        self,
        since_ts: int,
        sentiment: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._repo.get_high_impact(since_ts, sentiment, limit)

    def get_active_threads(self, since_ts: int, limit: int = 200) -> list[dict[str, Any]]:
        return self._repo.get_active_threads(since_ts, limit)

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        return self._repo.get_thread(thread_id)

    def get_thread_articles(
        self, thread_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        return self._repo.get_thread_articles(thread_id, limit)

    def get_thread_timeline(self, thread_id: str) -> list[dict[str, Any]]:
        return self._repo.get_thread_timeline(thread_id)

    def get_ticker_daily_stats(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        return self._repo.get_ticker_daily_stats(ticker, start_date, end_date)

    def article_count(self) -> int:
        row = self._repo.conn.execute("SELECT COUNT(*) FROM articles").fetchone()
        return int(row[0]) if row else 0

    def health_info(self) -> dict[str, Any]:
        settings = self.get_settings()
        return {
            "status": "ok",
            "storage": "sqlite",
            "db_path": str(self.db_path),
            "article_count": self.article_count(),
            "mode": settings.mode,
            "watchlist_count": len(self.get_watchlist()),
        }
