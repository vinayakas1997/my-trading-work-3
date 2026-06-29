"""Tests for cluster merge gates."""

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.post_enrichment.cosine_dedup.cluster import cluster_articles
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text


def _raw(headline: str, link: str) -> dict:
    return {
        "headline": headline,
        "summary": headline,
        "link": link,
        "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
        "source": "REUTERS",
        "region": "US",
        "tier": 2,
    }


def test_beat_vs_miss_stay_separate():
    beat = enrich_article(_raw("AAPL beats estimates on strong revenue", "https://ex.com/1"))
    miss = enrich_article(_raw("AAPL misses estimates on weak revenue", "https://ex.com/2"))
    for item in (beat, miss):
        item.norm_text = normalize_text(f"{item.article.headline} {item.article.summary}")
    entities = [item.article.entities() for item in (beat, miss)]
    clusters = cluster_articles([beat, miss], [beat.norm_text, miss.norm_text], entities)
    assert len(clusters) == 2
