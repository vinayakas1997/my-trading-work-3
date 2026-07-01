"""NewsService orchestrator for ingest and query."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from vinu_news.rss.config.feed_loader import load_feeds
from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.rss.fetch.parallel_fetcher import poll_all_feeds
from vinu_news.rss.storage.feed_health import update_feed_health
from vinu_news.analysis.pipeline import process_batch
from vinu_news.config import VinuConfig, load_config
from vinu_news.collection.filter import filter_leads_for_mode
from vinu_news.providers.registry import TickerNewsRegistry
from vinu_news.settings.store import SettingsView
from vinu_news.storage.base import StorageBackend
from vinu_news.storage.factory import create_storage
from vinu_news.net import request as http_request

LOG = logging.getLogger(__name__)


def _run_auto_analysis_batch(
    db_path: Path, config: VinuConfig, links: list[str], concurrency: int
) -> None:
    """Background worker: deep-analyze newly ingested links via the LLM.

    Runs off the main ingest thread so a slow/unreachable LLM never delays
    fetching or the next poll cycle. Each worker opens its own DB
    connection since sqlite3 connections aren't safe to share across
    threads.
    """
    from vinu_news.analysis.llm.analyze import analyze_article
    from vinu_news.analysis.storage.repository import NewsRepository

    def _one(link: str) -> None:
        repo = NewsRepository(db_path)
        try:
            analyze_article(repo, link, config=config)
        except Exception:
            LOG.warning("Auto LLM analysis failed for %s", link, exc_info=True)
        finally:
            repo.close()

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        list(pool.map(_one, links))


@dataclass
class IngestionCycleResult:
    feeds_polled: int
    feeds_failed: int
    raw_count: int
    enriched_count: int
    leads_before_filter: int
    leads_after_filter: int
    inserted: int
    clusters_found: int
    duplicates_dropped: int
    url_dedup_dropped: int
    url_skipped: int
    thread_matched_skipped: int
    threads_created: int
    threads_updated: int
    mode: str
    watchlist_size: int
    feed_results: list[FeedPollResult]

    def format_report(self) -> str:
        lines = [
            f"Mode: {self.mode} (watchlist: {self.watchlist_size} tickers)",
            f"Feeds polled: {self.feeds_polled}",
            f"Feeds failed/empty: {self.feeds_failed}",
            f"Raw articles: {self.raw_count}",
            f"URL dedup dropped (batch): {self.url_dedup_dropped}",
            f"Enriched: {self.enriched_count}",
            f"Leads before filter: {self.leads_before_filter}",
            f"Leads after filter: {self.leads_after_filter}",
            f"Clusters found: {self.clusters_found}",
            f"Duplicates dropped (batch): {self.duplicates_dropped}",
            f"New DB inserts: {self.inserted}",
            f"URL skipped (DB): {self.url_skipped}",
            f"Thread matched skipped: {self.thread_matched_skipped}",
            f"Threads created: {self.threads_created}",
            f"Threads updated: {self.threads_updated}",
        ]
        for result in self.feed_results:
            status = "OK" if result.article_count else f"FAIL({result.error})"
            lines.append(
                f"  - {result.feed_id}: {result.article_count} articles [{status}]"
            )
        return "\n".join(lines)


class NewsService:
    """Facade over storage, settings, watchlist, and ingestion pipeline."""

    def __init__(
        self,
        storage: StorageBackend | None = None,
        config: VinuConfig | None = None,
    ) -> None:
        self._config = config or load_config()
        self._storage = storage or create_storage(
            storage=self._config.storage,
            db_path=self._config.db_path,
            database_url=self._config.database_url,
        )
        self._owns_storage = storage is None

    def _stock_client(self):
        from vinu_news.integrations.stock_price import StockPriceClient

        return StockPriceClient(self._config.stock_api_url)

    def _maybe_auto_analyze(self, links: list[str], settings: SettingsView) -> None:
        if not links or settings.llm_analysis_mode != "auto":
            return
        from vinu_news.analysis.llm.client import LlmClient

        if not LlmClient(self._config).is_configured():
            return
        thread = threading.Thread(
            target=_run_auto_analysis_batch,
            args=(self._config.db_path, self._config, links, settings.llm_analysis_concurrency),
            daemon=True,
        )
        thread.start()

    def _enrich_with_price_reaction(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from vinu_news.analysis.post_enrichment.price_reaction import enrich_article_with_reaction

        client = self._stock_client()
        conn = self._storage.repo.conn
        return [enrich_article_with_reaction(conn, row, client) for row in rows]

    @property
    def storage(self) -> StorageBackend:
        return self._storage

    def close(self) -> None:
        if self._owns_storage:
            self._storage.close()

    def __enter__(self) -> NewsService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_settings(self) -> SettingsView:
        return self._storage.get_settings()

    def patch_settings(
        self,
        *,
        mode: str | None = None,
        poll_interval_sec: int | None = None,
        llm_analysis_mode: str | None = None,
        llm_analysis_concurrency: int | None = None,
    ) -> SettingsView:
        return self._storage.patch_settings(
            mode=mode,
            poll_interval_sec=poll_interval_sec,
            llm_analysis_mode=llm_analysis_mode,
            llm_analysis_concurrency=llm_analysis_concurrency,
        )

    def get_watchlist(self) -> list[str]:
        return self._storage.get_watchlist()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        return self._storage.add_watchlist_tickers(tickers)

    def remove_watchlist_ticker(self, ticker: str) -> bool:
        return self._storage.remove_watchlist_ticker(ticker)

    def pop_pending_ticker_fetch(self) -> list[str]:
        """Return tickers added since the last fetch, marking them handled."""
        pending = self._storage.list_pending_ticker_fetch()
        if pending:
            self._storage.clear_pending_ticker_fetch(pending)
        return pending

    def clear_all_pending_ticker_fetch(self) -> None:
        self._storage.clear_all_pending_ticker_fetch()

    def sync_watchlist_from_shared(self) -> dict[str, object]:
        path = self._config.shared_watchlist_path
        if path is None:
            return {"ok": False, "message": "VINU_SHARED_WATCHLIST_PATH not set", "added": []}
        added = self._storage.sync_watchlist_from_shared(path)
        return {"ok": True, "added": added, "tickers": self.get_watchlist()}

    def run_ingestion_cycle(
        self,
        *,
        feed_ids: list[str] | None = None,
        dry_run: bool = False,
        skip_post_process: bool = False,
    ) -> IngestionCycleResult:
        """Fetch RSS, enrich, filter by mode, persist leads."""
        settings = self._storage.get_settings()
        watchlist = set(self._storage.get_watchlist())

        feeds = load_feeds(feed_ids=feed_ids)
        raw_articles, feed_results = poll_all_feeds(feeds)
        feeds_failed = sum(1 for r in feed_results if r.article_count == 0)

        if dry_run:
            return IngestionCycleResult(
                feeds_polled=len(feeds),
                feeds_failed=feeds_failed,
                raw_count=len(raw_articles),
                enriched_count=0,
                leads_before_filter=0,
                leads_after_filter=0,
                inserted=0,
                clusters_found=0,
                duplicates_dropped=0,
                url_dedup_dropped=0,
                url_skipped=0,
                thread_matched_skipped=0,
                threads_created=0,
                threads_updated=0,
                mode=settings.mode,
                watchlist_size=len(watchlist),
                feed_results=feed_results,
            )

        update_feed_health(self._storage.repo, feed_results)

        result = process_batch(raw_articles, skip_post_process=skip_post_process)
        leads = result.articles
        leads_before = len(leads)

        if not skip_post_process:
            leads = filter_leads_for_mode(leads, settings.mode, watchlist)

        leads_after = len(leads)
        inserted = 0
        url_skipped = 0
        thread_matched_skipped = 0
        threads_created = 0
        threads_updated = 0

        if leads:
            if skip_post_process:
                inserted = self._storage.repo.upsert_batch(leads)
            else:
                persist_result = self._storage.persist_leads(leads)
                inserted = persist_result.inserted
                url_skipped = persist_result.url_skipped
                thread_matched_skipped = persist_result.thread_matched_skipped
                threads_created = persist_result.threads_created
                threads_updated = persist_result.threads_updated
                self._maybe_auto_analyze(persist_result.inserted_links, settings)

        return IngestionCycleResult(
            feeds_polled=len(feeds),
            feeds_failed=feeds_failed,
            raw_count=len(raw_articles),
            enriched_count=result.enriched_count,
            leads_before_filter=leads_before,
            leads_after_filter=leads_after,
            inserted=inserted,
            clusters_found=result.clusters_found,
            duplicates_dropped=result.duplicates_dropped,
            url_dedup_dropped=result.url_dedup_dropped,
            url_skipped=url_skipped,
            thread_matched_skipped=thread_matched_skipped,
            threads_created=threads_created,
            threads_updated=threads_updated,
            mode=settings.mode,
            watchlist_size=len(watchlist),
            feed_results=feed_results,
        )

    def run_ticker_news_ingest(
        self,
        *,
        tickers: list[str] | None = None,
        days: int = 7,
        dry_run: bool = False,
    ) -> IngestionCycleResult:
        """Fetch ticker-specific headlines and persist through enrichment pipeline."""
        settings = self._storage.get_settings()
        watchlist = tickers or self._storage.get_watchlist()
        if not watchlist:
            return IngestionCycleResult(
                feeds_polled=0,
                feeds_failed=0,
                raw_count=0,
                enriched_count=0,
                leads_before_filter=0,
                leads_after_filter=0,
                inserted=0,
                clusters_found=0,
                duplicates_dropped=0,
                url_dedup_dropped=0,
                url_skipped=0,
                thread_matched_skipped=0,
                threads_created=0,
                threads_updated=0,
                mode=settings.mode,
                watchlist_size=0,
                feed_results=[],
            )

        from_ts = self.ts_days_ago(days)
        to_ts = int(datetime.now(timezone.utc).timestamp())
        registry = TickerNewsRegistry(self._config)
        raw_articles: list[dict] = []
        for symbol in watchlist:
            raw_articles.extend(registry.fetch_for_ticker(symbol, from_ts, to_ts))

        if dry_run:
            return IngestionCycleResult(
                feeds_polled=len(watchlist),
                feeds_failed=0,
                raw_count=len(raw_articles),
                enriched_count=0,
                leads_before_filter=0,
                leads_after_filter=0,
                inserted=0,
                clusters_found=0,
                duplicates_dropped=0,
                url_dedup_dropped=0,
                url_skipped=0,
                thread_matched_skipped=0,
                threads_created=0,
                threads_updated=0,
                mode=settings.mode,
                watchlist_size=len(watchlist),
                feed_results=[],
            )

        result = process_batch(raw_articles)
        leads = filter_leads_for_mode(result.articles, settings.mode, set(watchlist))
        inserted = 0
        url_skipped = 0
        thread_matched_skipped = 0
        threads_created = 0
        threads_updated = 0
        if leads:
            persist_result = self._storage.persist_leads(leads)
            inserted = persist_result.inserted
            url_skipped = persist_result.url_skipped
            thread_matched_skipped = persist_result.thread_matched_skipped
            threads_created = persist_result.threads_created
            threads_updated = persist_result.threads_updated
            self._maybe_auto_analyze(persist_result.inserted_links, settings)

        return IngestionCycleResult(
            feeds_polled=len(watchlist),
            feeds_failed=0,
            raw_count=len(raw_articles),
            enriched_count=result.enriched_count,
            leads_before_filter=len(result.articles),
            leads_after_filter=len(leads),
            inserted=inserted,
            clusters_found=result.clusters_found,
            duplicates_dropped=result.duplicates_dropped,
            url_dedup_dropped=result.url_dedup_dropped,
            url_skipped=url_skipped,
            thread_matched_skipped=thread_matched_skipped,
            threads_created=threads_created,
            threads_updated=threads_updated,
            mode=settings.mode,
            watchlist_size=len(watchlist),
            feed_results=[],
        )

    def health(self) -> dict[str, Any]:
        info = self._storage.health_info()
        info["llm_model"] = self._config.llm_model
        
        # Check if LLM is active
        llm_active = False
        if self._config.llm_base_url:
            try:
                res = http_request(
                    "GET", self._config.llm_base_url.rstrip("/") + "/models", timeout=1.0
                )
                if res.status_code == 200:
                    llm_active = True
            except Exception:
                pass
        info["llm_active"] = llm_active
        return info

    @staticmethod
    def ts_days_ago(days: int) -> int:
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return int(dt.timestamp())

    @staticmethod
    def date_range_days(days: int) -> tuple[str, str]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=max(0, days - 1))
        return start.isoformat(), end.isoformat()

    def get_latest(
        self,
        limit: int = 20,
        date: str | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._storage.get_latest(limit, date=date, provider=provider)

    def get_articles_since(self, since_ts: int, limit: int = 100) -> list[dict[str, Any]]:
        return self._storage.get_articles_since(since_ts, limit)

    def get_ticker_news(
        self,
        symbol: str,
        *,
        days: int = 7,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        start_ts = self.ts_days_ago(days)
        rows = self._storage.get_news_for_ticker(symbol, start_ts, None, limit)
        return self._enrich_with_price_reaction(rows)

    def analyze_article(self, url_or_id: str) -> dict[str, Any]:
        from vinu_news.analysis.llm.analyze import analyze_article as llm_analyze
        from vinu_news.analysis.llm.client import LlmClientError

        try:
            return llm_analyze(self._storage.repo, url_or_id, config=self._config)
        except LlmClientError as exc:
            raise RuntimeError(str(exc)) from exc

    def get_watchlist_news(
        self,
        *,
        days: int = 7,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        tickers = self._storage.get_watchlist()
        start_ts = self.ts_days_ago(days)
        return self._storage.get_news_for_watchlist(tickers, start_ts, limit)

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._storage.search_articles(query, limit)

    def get_high_impact(
        self,
        *,
        hours: int = 24,
        sentiment: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        since_ts = int(
            (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
        )
        return self._storage.get_high_impact(since_ts, sentiment, limit)

    def get_active_threads(
        self,
        *,
        hours: int = 48,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        since_ts = int(
            (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
        )
        return self._storage.get_active_threads(since_ts, limit)

    def get_thread_detail(
        self,
        thread_id: str,
        *,
        limit: int = 50,
    ) -> dict[str, Any] | None:
        thread = self._storage.get_thread(thread_id)
        if not thread:
            return None
        articles = self._enrich_with_price_reaction(
            self._storage.get_thread_articles(thread_id, limit)
        )
        return {"thread": thread, "articles": articles}

    def get_thread_timeline(self, thread_id: str) -> list[dict[str, Any]]:
        rows = self._storage.get_thread_timeline(thread_id)
        return self._enrich_with_price_reaction(rows)

    def get_ticker_stats(
        self,
        symbol: str,
        *,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        start_date, end_date = self.date_range_days(days)
        return self._storage.get_ticker_daily_stats(symbol, start_date, end_date)
