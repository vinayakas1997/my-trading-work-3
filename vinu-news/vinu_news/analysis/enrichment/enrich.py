"""Orchestrates the 9 Fincept enrichment stages plus ticker dominance."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from vinu_news.analysis.enrichment.article_splitter import build_ticker_mentions
from vinu_news.analysis.enrichment.category import refine_category
from vinu_news.analysis.enrichment.impact import classify_impact
from vinu_news.analysis.enrichment.language import detect_language
from vinu_news.analysis.enrichment.priority import classify_priority
from vinu_news.analysis.enrichment.sentiment import score_sentiment
from vinu_news.analysis.enrichment.source_credibility import check_source_flag
from vinu_news.analysis.enrichment.summary_cleaner import clean_summary
from vinu_news.analysis.enrichment.threat import classify_threat
from vinu_news.analysis.enrichment.ticker_dominance import compute_dominance
from vinu_news.analysis.enrichment.ticker_extractor import extract_tickers
from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle
from vinu_news.analysis.storage.repository import parse_pub_date


def article_id_from_link(link: str) -> str:
    """Generate stable article id from URL."""
    return hashlib.sha256(link.encode("utf-8")).hexdigest()


def enrich_article(raw: dict[str, Any]) -> EnrichedArticle:
    """
    Run full enrichment pipeline on a raw article dict.

    Expected keys: headline, summary, link, pubDate, source, region, tier.
    Optional: category (feed default, defaults to MARKETS).
    """
    headline = raw.get("headline", "")
    summary_raw = raw.get("summary", "")
    link = raw.get("link", "")
    source = raw.get("source", "")
    region = raw.get("region", "GLOBAL")
    tier = int(raw.get("tier", 4))
    feed_category = raw.get("category", "MARKETS")

    cleaned_summary = clean_summary(summary_raw)
    combined = f"{headline} {cleaned_summary}"

    priority = classify_priority(combined)
    sentiment_result = score_sentiment(combined)
    sentiment = sentiment_result["sentiment"]
    sentiment_score = sentiment_result["sentiment_score"]
    impact = classify_impact(priority, sentiment_score)
    category = refine_category(combined, default=feed_category)
    tickers = extract_tickers(headline, cleaned_summary)
    lang = detect_language(headline)
    threat = classify_threat(combined, sentiment)
    source_flag = check_source_flag(source)
    sort_ts = parse_pub_date(raw.get("pubDate", ""))

    article_id = article_id_from_link(link) if link else hashlib.sha256(
        f"{headline}:{sort_ts}".encode()
    ).hexdigest()

    record = ArticleRecord(
        id=article_id,
        headline=headline,
        summary=cleaned_summary,
        source=source,
        link=link,
        sort_ts=sort_ts,
        region=region,
        tier=tier,
        category=category,
        priority=priority,
        sentiment=sentiment,
        sentiment_score=sentiment_score,
        impact=impact,
        tickers=json.dumps(tickers),
        lang=lang,
        threat_level=threat["threat_level"],
        threat_cat=threat["threat_cat"],
        threat_conf=threat["threat_conf"],
        source_flag=source_flag,
        entities_json="{}",
        cluster_id=None,
        is_lead=1,
    )

    dominance = compute_dominance(tickers, headline, cleaned_summary)
    mentions = build_ticker_mentions(article_id, dominance)

    return EnrichedArticle(article=record, mentions=mentions)


def enrich_batch(raw_articles: list[dict[str, Any]]) -> list[EnrichedArticle]:
    """Enrich a list of raw articles."""
    return [enrich_article(raw) for raw in raw_articles]
