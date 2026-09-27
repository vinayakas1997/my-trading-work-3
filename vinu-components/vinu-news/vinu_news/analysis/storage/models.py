"""Data models for enriched articles, threads, and analytics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ArticleRecord:
    id: str
    headline: str
    summary: str
    source: str
    link: str
    sort_ts: int
    region: str
    tier: int
    category: str
    priority: str
    sentiment: str
    sentiment_score: int
    impact: str
    tickers: str  # JSON array string
    lang: str
    threat_level: str
    threat_cat: str
    threat_conf: float
    source_flag: int
    entities_json: str = "{}"
    cluster_id: str | None = None
    is_lead: int = 1
    thread_id: str | None = None
    finbert_score: float | None = None
    finbert_label: str | None = None
    # item #19 (vinu-news finding #1): `sort_ts` alone silently conflated
    # publish time and ingestion time, with `parse_pub_date()`'s fallback
    # to "now" leaving no record that a substitution happened -- a
    # genuine, silent look-ahead-bias risk (an article fetched hours
    # after real publication would look, to any point-in-time replay, as
    # if it was published at fetch time). `published_at` is the real
    # parsed pubDate (nullable -- absent exactly when estimation
    # happened), `ingested_at` is always set to when this system actually
    # processed the article, never estimated, and
    # `publish_time_is_estimated` flags every case where `published_at`
    # had to be estimated so downstream point-in-time replay can exclude
    # them. `sort_ts` is kept as-is (not removed) so existing readers
    # don't all need to migrate to the new fields at once.
    published_at: int | None = None
    ingested_at: int = 0
    publish_time_is_estimated: bool = False

    def tickers_list(self) -> list[str]:
        return json.loads(self.tickers)

    def entities(self) -> dict[str, Any]:
        return json.loads(self.entities_json)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TickerMention:
    id: str
    article_id: str
    ticker: str
    dominance: float
    is_primary: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnrichedArticle:
    article: ArticleRecord
    mentions: list[TickerMention] = field(default_factory=list)
    norm_text: str = ""  # synonym-normalized text for dedup/thread matching

    def to_dict(self) -> dict[str, Any]:
        return {
            "article": self.article.to_dict(),
            "mentions": [m.to_dict() for m in self.mentions],
            "norm_text": self.norm_text,
        }


@dataclass
class StoryThread:
    thread_id: str
    first_seen_at: int
    last_seen_at: int
    article_count: int
    lead_headline: str
    dominant_ticker: str | None
    entities_json: str
    category: str
    last_article_id: str | None
    norm_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ThreadDailySnapshot:
    thread_id: str
    date: str
    article_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    flash_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TickerDailyStats:
    ticker: str
    date: str
    article_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    top_thread_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeedHealthRecord:
    feed_id: str
    last_success_at: int | None
    last_failure_at: int | None
    fail_streak: int
    total_polls: int
    total_failures: int
    avg_latency_ms: float
    last_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
