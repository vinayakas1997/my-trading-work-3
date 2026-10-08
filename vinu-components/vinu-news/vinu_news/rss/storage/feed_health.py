"""Feed health tracking in the shared news database (one row per source; see vinu_news/sources/health.py)."""

from __future__ import annotations

from vinu_news.analysis.storage.repository import NewsRepository
from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.sources.health import KIND_RSS, SourceHealth


def update_feed_health(
    repo: NewsRepository,
    feed_results: list[FeedPollResult],
) -> None:
    """Record each feed's poll outcome. An empty answer with no error is not a failure (a quiet feed is normal);
    only errors count toward the automatic switch-off."""
    health = SourceHealth(repo)
    for result in feed_results:
        health.record(
            result.feed_id,
            ok=result.error is None,
            error=result.error,
            kind=KIND_RSS,
            duration_ms=result.duration_ms,
            articles=result.article_count,
        )
