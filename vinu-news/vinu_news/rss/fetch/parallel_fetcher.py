"""Parallel feed polling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from vinu_news.rss.config.feed_loader import FeedConfig
from vinu_news.rss.config.settings import MAX_WORKERS
from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.rss.orchestration.feed_poller import poll_feed


def poll_all_feeds(feeds: list[FeedConfig]) -> tuple[list[dict], list[FeedPollResult]]:
    """Poll all feeds in parallel; return merged raw articles and per-feed results."""
    if not feeds:
        return [], []

    results: list[FeedPollResult] = []
    raw_articles: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(feeds))) as executor:
        future_map = {executor.submit(poll_feed, feed): feed for feed in feeds}
        for future in as_completed(future_map):
            result = future.result()
            results.append(result)
            raw_articles.extend(result.articles)

    return raw_articles, results
