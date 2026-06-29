"""Tests for cosine similarity clustering."""

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.post_enrichment.cosine_dedup.cluster import cluster_articles
from vinu_news.analysis.post_enrichment.cosine_dedup.vectorize import cosine_similarity
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


def test_similar_headlines_same_cluster():
    a = enrich_article(_raw("Fed raises interest rates by 25 basis points", "https://ex.com/1"))
    b = enrich_article(_raw("Federal Reserve raises interest rates 25 bps", "https://ex.com/2"))
    texts = [
        normalize_text(f"{a.article.headline} {a.article.summary}"),
        normalize_text(f"{b.article.headline} {b.article.summary}"),
    ]
    clusters = cluster_articles([a, b], texts)
    assert len(clusters) == 1
    assert len(clusters[0].members) == 2


def test_dissimilar_headlines_different_clusters():
    a = enrich_article(_raw("Apple launches new iPhone model", "https://ex.com/3"))
    b = enrich_article(_raw("Oil prices surge on OPEC cut news", "https://ex.com/4"))
    texts = [
        normalize_text(f"{a.article.headline} {a.article.summary}"),
        normalize_text(f"{b.article.headline} {b.article.summary}"),
    ]
    clusters = cluster_articles([a, b], texts)
    assert len(clusters) == 2


def test_cosine_identical_vectors():
    vec = {"fed": 0.5, "rate": 0.3}
    assert cosine_similarity(vec, vec) == 1.0
