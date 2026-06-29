"""Full ingestion pipeline: fetch, enrich, post-process, persist."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vinu_news.rss.config.feed_loader import load_feeds
from vinu_news.rss.fetch.parallel_fetcher import poll_all_feeds
from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.rss.storage.feed_health import update_feed_health
from vinu_news.analysis.pipeline import process_batch
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.analysis.storage.repository import NewsRepository


@dataclass
class IngestionSummary:
    feeds_polled: int
    feeds_failed: int
    raw_count: int
    enriched_count: int
    inserted: int
    clusters_found: int
    duplicates_dropped: int
    url_dedup_dropped: int
    url_skipped: int
    thread_matched_skipped: int
    threads_created: int
    threads_updated: int
    feed_results: list[FeedPollResult]

    def format_report(self) -> str:
        lines = [
            f"Feeds polled: {self.feeds_polled}",
            f"Feeds failed/empty: {self.feeds_failed}",
            f"Raw articles: {self.raw_count}",
            f"URL dedup dropped (batch): {self.url_dedup_dropped}",
            f"Enriched: {self.enriched_count}",
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


def run_ingestion(
    db_path: str | Path | None = None,
    feed_ids: list[str] | None = None,
    dry_run: bool = False,
    skip_post_process: bool = False,
) -> IngestionSummary:
    """Fetch all feeds, enrich, post-process, and optionally persist to SQLite."""
    feeds = load_feeds(feed_ids=feed_ids)
    raw_articles, feed_results = poll_all_feeds(feeds)

    feeds_failed = sum(1 for r in feed_results if r.article_count == 0)

    if not dry_run:
        with NewsRepository(db_path) as repo:
            update_feed_health(repo, feed_results)

    if dry_run:
        return IngestionSummary(
            feeds_polled=len(feeds),
            feeds_failed=feeds_failed,
            raw_count=len(raw_articles),
            enriched_count=0,
            inserted=0,
            clusters_found=0,
            duplicates_dropped=0,
            url_dedup_dropped=0,
            url_skipped=0,
            thread_matched_skipped=0,
            threads_created=0,
            threads_updated=0,
            feed_results=feed_results,
        )

    result = process_batch(raw_articles, skip_post_process=skip_post_process)

    inserted = 0
    url_skipped = 0
    thread_matched_skipped = 0
    threads_created = 0
    threads_updated = 0

    if result.articles:
        with NewsRepository(db_path) as repo:
            if skip_post_process:
                inserted = repo.upsert_batch(result.articles)
            else:
                persist_result = persist_leads(repo, result.articles)
                inserted = persist_result.inserted
                url_skipped = persist_result.url_skipped
                thread_matched_skipped = persist_result.thread_matched_skipped
                threads_created = persist_result.threads_created
                threads_updated = persist_result.threads_updated

    return IngestionSummary(
        feeds_polled=len(feeds),
        feeds_failed=feeds_failed,
        raw_count=len(raw_articles),
        enriched_count=result.enriched_count,
        inserted=inserted,
        clusters_found=result.clusters_found,
        duplicates_dropped=result.duplicates_dropped,
        url_dedup_dropped=result.url_dedup_dropped,
        url_skipped=url_skipped,
        thread_matched_skipped=thread_matched_skipped,
        threads_created=threads_created,
        threads_updated=threads_updated,
        feed_results=feed_results,
    )
