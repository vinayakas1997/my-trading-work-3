"""Fetch package."""

from vinu_news.rss.fetch.fetch_result import FeedPollResult, FetchResult
from vinu_news.rss.fetch.http_client import fetch_url
from vinu_news.rss.fetch.parallel_fetcher import poll_all_feeds
from vinu_news.rss.fetch.response_validator import is_valid_feed_body

__all__ = [
    "FeedPollResult",
    "FetchResult",
    "fetch_url",
    "is_valid_feed_body",
    "poll_all_feeds",
]
