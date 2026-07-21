"""SQLite storage backend wrapping NewsRepository."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from vinu_news.analysis.storage.models import EnrichedArticle
from vinu_news.analysis.storage.persist import PersistResult, persist_leads
from vinu_news.analysis.storage.repository import ARTICLE_COLUMNS, NewsRepository

from vinu_news.backfill.store import BackfillStore, BackfillStatusView
from vinu_news.config import settings_env_defaults
from vinu_news.settings.store import PollStatusView, SettingsStore, SettingsView
from vinu_news.watchlist.store import WatchlistStore

_SETTINGS_SCHEMA = (
    Path(__file__).resolve().parent.parent / "settings" / "schema.sql"
)
_WATCHLIST_SCHEMA = (
    Path(__file__).resolve().parent.parent / "watchlist" / "schema.sql"
)
_BACKFILL_SCHEMA = (
    Path(__file__).resolve().parent.parent / "backfill" / "schema.sql"
)


class SqliteBackend:
    """SQLite implementation with vinu settings and watchlist tables.

    Each thread gets its own connection via NewsRepository's thread-local
    pattern, and SettingsStore/WatchlistStore are lazily created per thread.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._repo = NewsRepository(db_path)
        self.db_path = self._repo.db_path
        self._local = threading.local()
        self._init_vinu_schema()

    @property
    def repo(self) -> NewsRepository:
        return self._repo

    @property
    def _settings(self) -> SettingsStore:
        if not hasattr(self._local, "_settings"):
            self._local._settings = SettingsStore(self._repo.conn)
        return self._local._settings

    @property
    def _watchlist(self) -> WatchlistStore:
        if not hasattr(self._local, "_watchlist"):
            self._local._watchlist = WatchlistStore(self._repo.conn)
        return self._local._watchlist

    @property
    def _backfill(self) -> BackfillStore:
        if not hasattr(self._local, "_backfill"):
            self._local._backfill = BackfillStore(self._repo.conn)
        return self._local._backfill

    def _init_vinu_schema(self) -> None:
        env_defaults = settings_env_defaults()
        self._settings.init_schema(
            _SETTINGS_SCHEMA.read_text(encoding="utf-8"),
            env_defaults=env_defaults,
        )
        self._watchlist.init_schema(_WATCHLIST_SCHEMA.read_text(encoding="utf-8"))
        self._backfill.init_schema(_BACKFILL_SCHEMA.read_text(encoding="utf-8"))
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
        llm_analysis_mode: str | None = None,
        llm_analysis_concurrency: int | None = None,
        active_tiers: list[int] | None = None,
        backfill_start_date: str | None = None,
        backfill_pause_on_error: bool | None = None,
    ) -> SettingsView:
        return self._settings.patch(
            mode=mode,
            poll_interval_sec=poll_interval_sec,
            llm_analysis_mode=llm_analysis_mode,
            llm_analysis_concurrency=llm_analysis_concurrency,
            active_tiers=active_tiers,
            backfill_start_date=backfill_start_date,
            backfill_pause_on_error=backfill_pause_on_error,
        )

    def get_poll_status(self) -> PollStatusView:
        return self._settings.get_poll_status()

    def set_poll_status(self, **fields: int | None) -> None:
        self._settings.set_poll_status(**fields)

    def get_watchlist(self) -> list[str]:
        return self._watchlist.list_tickers()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        return self._watchlist.add_tickers(tickers)

    def remove_watchlist_ticker(self, ticker: str) -> bool:
        return self._watchlist.remove_ticker(ticker)

    def list_pending_ticker_fetch(self) -> list[str]:
        return self._watchlist.list_pending()

    def clear_pending_ticker_fetch(self, tickers: list[str]) -> None:
        self._watchlist.clear_pending(tickers)

    def clear_all_pending_ticker_fetch(self) -> None:
        self._watchlist.clear_all_pending()

    def sync_watchlist_from_shared(self, path: Path) -> list[str]:
        from vinu_news.watchlist.shared import sync_from_shared

        return sync_from_shared(self._watchlist, path)

    def persist_leads(self, leads: list[EnrichedArticle]) -> PersistResult:
        return persist_leads(self._repo, leads)

    def get_latest(
        self,
        limit: int = 20,
        date: str | None = None,
        provider: str | None = None,
        tiers: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT a.*, n.analysis_json AS llm_analysis
            FROM articles a
            LEFT JOIN news_analysis n ON a.link = n.url
            WHERE a.is_lead = 1
        """
        params = []
        if date:
            query += " AND date(a.sort_ts, 'unixepoch') = ?"
            params.append(date)
        if provider and provider.lower() != "all":
            query += " AND UPPER(a.source) = ?"
            params.append(provider.upper())
        if tiers is not None:
            placeholders = ",".join("?" for _ in tiers)
            query += f" AND a.tier IN ({placeholders})"
            params.extend(tiers)

        query += " ORDER BY a.sort_ts DESC LIMIT ?"
        params.append(limit)

        rows = self._repo.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_articles_since(self, since_ts: int, limit: int = 100) -> list[dict[str, Any]]:
        cols = ", ".join(ARTICLE_COLUMNS)
        rows = self._repo.conn.execute(
            f"""
            SELECT {cols} FROM articles
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
        placeholders = ", ".join("?" for _ in tickers)
        query = f"""
            SELECT a.*, m.ticker AS mention_ticker, m.dominance, m.is_primary, n.analysis_json AS llm_analysis
            FROM article_ticker_mentions m
            JOIN articles a ON a.id = m.article_id
            LEFT JOIN news_analysis n ON a.link = n.url
            WHERE m.ticker IN ({placeholders})
        """
        params: list[Any] = [t.upper() for t in tickers]
        if start_ts is not None:
            query += " AND a.sort_ts >= ?"
            params.append(start_ts)
        query += " ORDER BY a.sort_ts DESC LIMIT ?"
        params.append(limit)

        rows = self._repo.conn.execute(query, params).fetchall()
        seen: set[str] = set()
        combined: list[dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            article_id = d["id"]
            if article_id in seen:
                continue
            seen.add(article_id)
            combined.append(d)
        return combined

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

    def get_backfill_status_all(self) -> list[BackfillStatusView]:
        return self._backfill.get_all()

    def get_backfill_status(self, ticker: str) -> BackfillStatusView | None:
        return self._backfill.get(ticker)

    def toggle_backfill(self, ticker: str, enabled: bool) -> None:
        self._backfill.toggle(ticker, enabled)

    def ensure_backfill_ticker(self, ticker: str) -> None:
        self._backfill.ensure_ticker(ticker)

    def update_backfill_progress(
        self,
        ticker: str,
        backfilled_up_to_ts: int,
        article_count: int,
        oldest_ts: int | None = None,
        error_message: str | None = None,
        status: str = "in_progress",
    ) -> None:
        fields = {
            "status": status,
            "backfilled_up_to_ts": backfilled_up_to_ts,
            "article_count": article_count,
            "updated_at": int(__import__("time").time()),
        }
        if oldest_ts is not None:
            fields["oldest_ts"] = oldest_ts
        if error_message is not None:
            fields["error_message"] = error_message
        self._backfill.upsert(ticker, **fields)

    def mark_backfill_completed(self, ticker: str) -> None:
        self._backfill.upsert(
            ticker,
            status="completed",
            updated_at=int(__import__("time").time()),
        )

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
