"""NewsService orchestrator for ingest and query."""

from __future__ import annotations

import logging
import queue
import threading
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
from vinu_news.settings.store import PollStatusView, SettingsView
from vinu_news.storage.base import StorageBackend
from vinu_news.storage.factory import create_storage
from vinu_news.net import request as http_request

_BACKFILL_CHUNK_DAYS = 30
_BACKFILL_START_DEFAULT_TS = int(
    datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp()
)

LOG = logging.getLogger(__name__)


class AutoAnalysisWorker:
    """Thread-safe background worker for LLM analysis with rate limiting.
    
    Uses a fixed pool of worker threads that pull from a shared queue,
    preventing LLM overload and providing predictable resource usage.
    """
    
    def __init__(
        self,
        db_path: Path,
        config: VinuConfig,
        concurrency: int,
        queue_maxsize: int = 1000,
    ):
        self.db_path = db_path
        self.config = config
        self.concurrency = max(1, concurrency)
        self.queue: queue.Queue[str] = queue.Queue(maxsize=queue_maxsize)
        self.running = False
        self.workers: list[threading.Thread] = []
        
        # Start worker threads
        self._start_workers()
    
    def _start_workers(self) -> None:
        """Start fixed pool of worker threads."""
        self.running = True
        for _ in range(self.concurrency):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"llm-analysis-worker",
            )
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self) -> None:
        """Worker loop: pull links from queue and analyze."""
        from vinu_news.analysis.llm.analyze import analyze_article
        from vinu_news.analysis.storage.repository import NewsRepository
        
        while self.running:
            try:
                # Wait for work with timeout to allow graceful shutdown
                link = self.queue.get(timeout=1.0)
            except queue.Empty:
                continue
            
            try:
                repo = NewsRepository(self.db_path)
                try:
                    analyze_article(repo, link, config=self.config)
                finally:
                    repo.close()
            except Exception:
                LOG.warning("Auto LLM analysis failed for %s", link, exc_info=True)
            finally:
                self.queue.task_done()
    
    def submit(self, link: str) -> bool:
        """Submit a link for analysis. Returns False if queue is full."""
        try:
            self.queue.put_nowait(link)
            return True
        except queue.Full:
            LOG.warning("Analysis queue full, skipping analysis for %s", link)
            return False
    
    def shutdown(self) -> None:
        """Gracefully shutdown workers."""
        self.running = False
        # Wait for queue to drain
        self.queue.join()
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5.0)
        self.workers.clear()

    def backfill_unanalyzed(self, limit: int = 500) -> int:
        """Find articles missing LLM analysis and submit them to the queue.
        
        Returns the number of articles submitted.
        """
        from vinu_news.analysis.storage.repository import NewsRepository

        repo = NewsRepository(self.db_path)
        try:
            rows = repo.conn.execute(
                """
                SELECT a.link FROM articles a
                LEFT JOIN news_analysis n ON a.link = n.url
                WHERE n.url IS NULL
                ORDER BY a.sort_ts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            repo.close()

        if not rows:
            LOG.info("Backfill: no unanalyzed articles found")
            return 0

        submitted = 0
        for row in rows:
            link = row["link"]
            if link and self.submit(link):
                submitted += 1

        LOG.info(
            "Backfill: submitted %d / %d unanalyzed articles",
            submitted, len(rows),
        )
        return submitted


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
        self._stock_client_instance: Any | None = None
        self._auto_analysis_worker: AutoAnalysisWorker | None = None

        # Initialize auto-analysis worker from DB settings (with env fallback)
        try:
            db_settings = self._storage.get_settings()
            llm_analysis_mode = db_settings.llm_analysis_mode
            llm_analysis_concurrency = db_settings.llm_analysis_concurrency
        except Exception:
            llm_analysis_mode = self._config.llm_analysis_mode
            llm_analysis_concurrency = self._config.llm_analysis_concurrency

        if llm_analysis_mode == "auto":
            self._auto_analysis_worker = AutoAnalysisWorker(
                db_path=self._config.db_path,
                config=self._config,
                concurrency=llm_analysis_concurrency,
            )
            # Backfill any articles ingested while analysis was off
            self._auto_analysis_worker.backfill_unanalyzed()

    def _stock_client(self):
        if self._stock_client_instance is None:
            from vinu_news.integrations.stock_price import StockPriceClient

            self._stock_client_instance = StockPriceClient(self._config.stock_api_url)
        return self._stock_client_instance

    def _maybe_auto_analyze(self, links: list[str], settings: SettingsView) -> None:
        if not links or settings.llm_analysis_mode != "auto":
            return
        from vinu_news.analysis.llm.client import LlmClient

        if not LlmClient(self._config).is_configured():
            return
        if self._auto_analysis_worker is None:
            return

        # Submit links to the shared analysis queue
        for link in links:
            if not self._auto_analysis_worker.submit(link):
                LOG.warning("Analysis queue full, skipping analysis for remaining links")
                break

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
        if self._stock_client_instance is not None:
            self._stock_client_instance.close()
        if self._auto_analysis_worker is not None:
            self._auto_analysis_worker.shutdown()
            self._auto_analysis_worker = None

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
        active_tiers: list[int] | None = None,
        backfill_start_date: str | None = None,
        backfill_pause_on_error: bool | None = None,
    ) -> SettingsView:
        result = self._storage.patch_settings(
            mode=mode,
            poll_interval_sec=poll_interval_sec,
            llm_analysis_mode=llm_analysis_mode,
            llm_analysis_concurrency=llm_analysis_concurrency,
            active_tiers=active_tiers,
            backfill_start_date=backfill_start_date,
            backfill_pause_on_error=backfill_pause_on_error,
        )

        # If auto-analysis was enabled at runtime, start the worker
        if llm_analysis_mode == "auto" and self._auto_analysis_worker is None:
            self._auto_analysis_worker = AutoAnalysisWorker(
                db_path=self._config.db_path,
                config=self._config,
                concurrency=result.llm_analysis_concurrency,
            )
            # Backfill articles ingested while analysis was off
            self._auto_analysis_worker.backfill_unanalyzed()

        # If auto-analysis was disabled at runtime, shut down the worker
        if llm_analysis_mode == "manual" and self._auto_analysis_worker is not None:
            self._auto_analysis_worker.shutdown()
            self._auto_analysis_worker = None

        return result

    def get_poll_status(self) -> PollStatusView:
        return self._storage.get_poll_status()

    def set_poll_status(self, **fields: int | None) -> None:
        self._storage.set_poll_status(**fields)

    def get_watchlist(self) -> list[str]:
        return self._storage.get_watchlist()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        added = self._storage.add_watchlist_tickers(tickers)
        for t in added:
            self.ensure_ticker_backfill(t)
        self._export_watchlist_to_shared()
        return added

    def _export_watchlist_to_shared(self) -> None:
        path = self._config.shared_watchlist_path
        if path is None:
            return
        from vinu_news.watchlist.shared import write_shared

        write_shared(path, self.get_watchlist())

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
        for t in added:
            self.ensure_ticker_backfill(t)
        return {"ok": True, "added": added, "tickers": self.get_watchlist()}

    def get_backfill_status(self) -> list[dict]:
        return [s.to_dict() for s in self._storage.get_backfill_status_all()]

    def get_backfill_status_for(self, ticker: str) -> dict | None:
        v = self._storage.get_backfill_status(ticker)
        return v.to_dict() if v else None

    def toggle_backfill(self, ticker: str, enabled: bool) -> None:
        self._storage.toggle_backfill(ticker, enabled)

    def ensure_ticker_backfill(self, ticker: str) -> None:
        self._storage.ensure_backfill_ticker(ticker)

    def run_backfill_single(self, ticker: str) -> dict:
        ticker = ticker.upper()
        registry = TickerNewsRegistry(self._config)
        watchlist = set(self._storage.get_watchlist())
        settings = self._storage.get_settings()

        status = self._storage.get_backfill_status(ticker)
        if status is None:
            self._storage.ensure_backfill_ticker(ticker)
            status = self._storage.get_backfill_status(ticker)

        if status and not status.enabled:
            return {"ticker": ticker, "status": "skipped", "reason": "disabled"}

        if status and status.backfilled_up_to_ts:
            start_ts = status.backfilled_up_to_ts
        else:
            try:
                dt = datetime.strptime(settings.backfill_start_date, "%Y-%m-%d")
                start_ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
            except (ValueError, TypeError):
                start_ts = _BACKFILL_START_DEFAULT_TS

        end_ts = int(datetime.now(timezone.utc).timestamp())
        if start_ts >= end_ts:
            self._storage.mark_backfill_completed(ticker)
            return {"ticker": ticker, "status": "completed", "articles_fetched": 0}

        total_fetched = 0
        oldest_seen: int | None = None
        chunk_start = start_ts
        had_errors = False

        while chunk_start < end_ts:
            if status and not self._storage.get_backfill_status(ticker).enabled:
                return {"ticker": ticker, "status": "paused", "articles_fetched": total_fetched}

            chunk_end = min(chunk_start + _BACKFILL_CHUNK_DAYS * 86400, end_ts)
            raw_articles, errors = registry.fetch_for_ticker(ticker, chunk_start, chunk_end)

            if not raw_articles:
                if errors:
                    LOG.warning(
                        "Providers failed for %s [%d-%d), retrying once: %s",
                        ticker, chunk_start, chunk_end, errors,
                    )
                    raw_articles, errors = registry.fetch_for_ticker(ticker, chunk_start, chunk_end)
                if not raw_articles:
                    if errors:
                        LOG.error(
                            "Chunk [%d-%d) permanently failed for %s: %s",
                            chunk_start, chunk_end, ticker, errors,
                        )
                        had_errors = True
                        self._storage.update_backfill_progress(
                            ticker,
                            backfilled_up_to_ts=chunk_end,
                            article_count=total_fetched,
                            oldest_ts=oldest_seen,
                            error_message=f"providers_failed: {','.join(errors)}",
                        )
                    chunk_start = chunk_end
                    continue

            result = process_batch(raw_articles, watchlist=watchlist)
            leads = filter_leads_for_mode(result.articles, "all", watchlist)

            if leads:
                persist_result = self._storage.persist_leads(leads)
                total_fetched += persist_result.inserted
                if oldest_seen is None:
                    for a in leads:
                        ts = a.article.sort_ts
                        if oldest_seen is None or ts < oldest_seen:
                            oldest_seen = ts

            chunk_start = chunk_end
            self._storage.update_backfill_progress(
                ticker,
                backfilled_up_to_ts=chunk_end,
                article_count=total_fetched,
                oldest_ts=oldest_seen,
            )

        if had_errors:
            LOG.warning("Backfill for %s completed with provider errors", ticker)
        else:
            self._storage.mark_backfill_completed(ticker)
        return {
            "ticker": ticker,
            "status": "completed",
            "articles_fetched": total_fetched,
        }

    def run_backfill_all(self) -> list[dict]:
        results = []
        for entry in self._storage.get_backfill_status_all():
            if entry.enabled and entry.status != "completed":
                results.append(self.run_backfill_single(entry.ticker))
        return results

    def run_ingestion_cycle(
        self,
        *,
        source: str = "rss",
        feed_ids: list[str] | None = None,
        tickers: list[str] | None = None,
        days: int = 7,
        dry_run: bool = False,
    ) -> IngestionCycleResult:
        """Unified ingestion from RSS feeds or ticker-news providers.

        Args:
            source: "rss" (default) for RSS feeds, "ticker_news" for Yahoo ticker news.
            feed_ids: RSS feed IDs to poll (None = all active tiers).
            tickers: Tickers for ticker_news source (None = use watchlist).
            days: Lookback days for ticker_news source.
            dry_run: Report counts without persisting.
        """
        settings = self._storage.get_settings()
        watchlist = set(self._storage.get_watchlist())

        # --- Fetch phase (source-specific) ---
        if source == "rss":
            feeds = load_feeds(feed_ids=feed_ids, tiers=settings.active_tiers)
            raw_articles, feed_results = poll_all_feeds(feeds)
            feeds_polled = len(feeds)
            feeds_failed = sum(1 for r in feed_results if r.article_count == 0)
        elif source == "ticker_news":
            active_tickers = tickers or self._storage.get_watchlist()
            if not active_tickers:
                return IngestionCycleResult(
                    feeds_polled=0, feeds_failed=0, raw_count=0,
                    enriched_count=0, leads_before_filter=0, leads_after_filter=0,
                    inserted=0, clusters_found=0, duplicates_dropped=0,
                    url_dedup_dropped=0, url_skipped=0, thread_matched_skipped=0,
                    threads_created=0, threads_updated=0,
                    mode=settings.mode, watchlist_size=0, feed_results=[],
                )
            from_ts = self.ts_days_ago(days)
            to_ts = int(datetime.now(timezone.utc).timestamp())
            registry = TickerNewsRegistry(self._config)
            raw_articles: list[dict] = []
            feeds_failed = 0
            for symbol in active_tickers:
                articles, errors = registry.fetch_for_ticker(symbol, from_ts, to_ts)
                raw_articles.extend(articles)
                if errors:
                    feeds_failed += 1
                    LOG.warning("Ticker %s had provider errors: %s", symbol, errors)
            feed_results: list[FeedPollResult] = []
            feeds_polled = len(active_tickers)
        else:
            raise ValueError(f"Unknown source: {source}. Use 'rss' or 'ticker_news'.")

        if dry_run:
            return IngestionCycleResult(
                feeds_polled=feeds_polled, feeds_failed=feeds_failed,
                raw_count=len(raw_articles), enriched_count=0,
                leads_before_filter=0, leads_after_filter=0, inserted=0,
                clusters_found=0, duplicates_dropped=0, url_dedup_dropped=0,
                url_skipped=0, thread_matched_skipped=0, threads_created=0,
                threads_updated=0, mode=settings.mode,
                watchlist_size=len(watchlist), feed_results=feed_results,
            )

        # RSS-specific post-fetch
        if source == "rss":
            update_feed_health(self._storage.repo, feed_results)

        # --- Enrichment, filter, persist (shared) ---
        result = process_batch(
            raw_articles,
            watchlist=watchlist,
        )
        leads = result.articles
        leads_before = len(leads)

        leads = filter_leads_for_mode(leads, settings.mode, watchlist)

        leads_after = len(leads)
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
            feeds_polled=feeds_polled, feeds_failed=feeds_failed,
            raw_count=len(raw_articles), enriched_count=result.enriched_count,
            leads_before_filter=leads_before, leads_after_filter=leads_after,
            inserted=inserted, clusters_found=result.clusters_found,
            duplicates_dropped=result.duplicates_dropped,
            url_dedup_dropped=result.url_dedup_dropped,
            url_skipped=url_skipped,
            thread_matched_skipped=thread_matched_skipped,
            threads_created=threads_created, threads_updated=threads_updated,
            mode=settings.mode, watchlist_size=len(watchlist),
            feed_results=feed_results,
        )

    # Backward-compatible wrapper for ticker_news source
    def run_ticker_news_ingest(
        self,
        *,
        tickers: list[str] | None = None,
        days: int = 7,
        dry_run: bool = False,
    ) -> IngestionCycleResult:
        """Fetch ticker-specific headlines. Delegates to run_ingestion_cycle."""
        return self.run_ingestion_cycle(
            source="ticker_news", tickers=tickers, days=days, dry_run=dry_run,
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
        tiers: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        return self._storage.get_latest(limit, date=date, provider=provider, tiers=tiers)

    def get_articles_since(self, since_ts: int, limit: int = 100) -> list[dict[str, Any]]:
        return self._storage.get_articles_since(since_ts, limit)

    def get_ticker_news(
        self,
        symbol: str,
        *,
        days: int = 7,
        from_ts: int | None = None,
        to_ts: int | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if from_ts is None:
            start_ts = self.ts_days_ago(days)
        else:
            start_ts = from_ts
        rows = self._storage.get_news_for_ticker(symbol, start_ts, to_ts, limit)
        return self._enrich_with_price_reaction(rows)

    def analyze_article(self, url_or_id: str) -> dict[str, Any]:
        from vinu_news.analysis.llm.analyze import analyze_article as llm_analyze
        from vinu_news.analysis.llm.client import LlmClientError

        try:
            return llm_analyze(self._storage.repo, url_or_id, config=self._config)
        except LlmClientError as exc:
            raise RuntimeError(str(exc)) from exc

    def backfill_analysis(self, limit: int = 500) -> dict[str, Any]:
        """Submit unanalyzed articles to the LLM analysis queue."""
        if self._auto_analysis_worker is None:
            return {"submitted": 0, "error": "auto-analysis not enabled"}
        submitted = self._auto_analysis_worker.backfill_unanalyzed(limit=limit)
        return {"submitted": submitted}

    def backfill_finbert_sentiment(self, limit: int = 500) -> dict[str, Any]:
        """Score articles missing finbert_score with FinBERT (batched inference)."""
        from vinu_news.analysis.enrichment.finbert_sentiment import score_finbert_batch

        conn = self._storage.repo.conn
        rows = conn.execute(
            "SELECT id, headline, summary FROM articles WHERE finbert_score IS NULL "
            "ORDER BY sort_ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return {"scored": 0, "remaining": 0}

        ids = [r["id"] for r in rows]
        texts = [f"{r['headline']} {r['summary'] or ''}".strip() for r in rows]
        results = score_finbert_batch(texts)

        conn.executemany(
            "UPDATE articles SET finbert_score = ?, finbert_label = ? WHERE id = ?",
            [(r["finbert_score"], r["finbert_label"], aid) for r, aid in zip(results, ids)],
        )
        conn.commit()

        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM articles WHERE finbert_score IS NULL"
        ).fetchone()["n"]
        return {"scored": len(ids), "remaining": remaining}

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
