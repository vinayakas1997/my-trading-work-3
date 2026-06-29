"""Single-feed poll: fetch, validate, parse."""

from __future__ import annotations

import logging

from vinu_news.rss.config.feed_loader import FeedConfig
from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.rss.fetch.http_client import fetch_url
from vinu_news.rss.fetch.response_validator import is_valid_feed_body
from vinu_news.rss.parse.rss_parser import parse_feed_body

logger = logging.getLogger(__name__)


def poll_feed(feed: FeedConfig) -> FeedPollResult:
    """Fetch one feed and return raw articles or error metadata."""
    try:
        fetch = fetch_url(feed.url)

        if fetch.error and not fetch.body:
            logger.warning(
                "Feed %s failed: %s (duration=%sms)",
                feed.id,
                fetch.error,
                fetch.duration_ms,
            )
            return FeedPollResult(
                feed_id=feed.id,
                url=feed.url,
                status_code=fetch.status_code,
                articles=[],
                error=fetch.error,
                duration_ms=fetch.duration_ms,
            )

        valid, reason = is_valid_feed_body(fetch.body)
        if not valid:
            logger.warning(
                "Feed %s rejected: %s (status=%s)",
                feed.id,
                reason,
                fetch.status_code,
            )
            return FeedPollResult(
                feed_id=feed.id,
                url=feed.url,
                status_code=fetch.status_code,
                articles=[],
                error=reason,
                duration_ms=fetch.duration_ms,
            )

        articles = parse_feed_body(fetch.body, feed)
        logger.info(
            "Feed %s: %d articles (status=%s, duration=%sms)",
            feed.id,
            len(articles),
            fetch.status_code,
            fetch.duration_ms,
        )
        return FeedPollResult(
            feed_id=feed.id,
            url=feed.url,
            status_code=fetch.status_code,
            articles=articles,
            error=fetch.error,
            duration_ms=fetch.duration_ms,
        )
    except Exception as exc:
        logger.exception("Feed %s unexpected error: %s", feed.id, exc)
        return FeedPollResult(
            feed_id=feed.id,
            url=feed.url,
            status_code=None,
            articles=[],
            error=str(exc),
            duration_ms=0,
        )
