"""RSS/Atom parser using feedparser."""

from __future__ import annotations

import logging

import feedparser

from vinu_news.rss.config.feed_loader import FeedConfig
from vinu_news.rss.models.raw_article import RawArticle

logger = logging.getLogger(__name__)


def _entry_summary(entry: feedparser.FeedParserDict) -> str:
    if getattr(entry, "summary", None):
        return str(entry.summary)
    if getattr(entry, "description", None):
        return str(entry.description)
    content = getattr(entry, "content", None)
    if content and len(content) > 0 and content[0].get("value"):
        return str(content[0]["value"])
    return ""


def _entry_pub_date(entry: feedparser.FeedParserDict) -> str:
    if getattr(entry, "published", None):
        return str(entry.published)
    if getattr(entry, "updated", None):
        return str(entry.updated)
    return ""


def parse_feed_body(body: bytes, feed: FeedConfig) -> list[dict]:
    """Parse RSS/Atom bytes into pipeline-ready raw article dicts."""
    parsed = feedparser.parse(body)
    articles: list[dict] = []

    for entry in parsed.entries:
        try:
            headline = str(getattr(entry, "title", "") or "").strip()
            link = str(getattr(entry, "link", "") or "").strip()
            if not headline or not link:
                continue

            raw = RawArticle(
                headline=headline,
                summary=_entry_summary(entry),
                link=link,
                pubDate=_entry_pub_date(entry),
                source=feed.source,
                region=feed.region,
                tier=feed.tier,
                category=feed.category,
            )
            articles.append(raw.to_pipeline_dict())
        except Exception as exc:
            logger.warning(
                "Skipping malformed entry in feed %s: %s",
                feed.id,
                exc,
            )
            continue

    return articles
