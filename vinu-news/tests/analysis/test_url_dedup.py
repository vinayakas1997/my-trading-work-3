"""Tests for in-batch URL deduplication."""

from vinu_news.analysis.pre_enrichment.url_dedup import dedup_urls_batch


def test_dedup_urls_batch_keeps_first():
    articles = [
        {"link": "https://Example.com/story/", "headline": "A"},
        {"link": "https://example.com/story", "headline": "B"},
        {"link": "https://example.com/other", "headline": "C"},
    ]
    result = dedup_urls_batch(articles)
    assert len(result) == 2
    assert result[0]["headline"] == "A"
    assert result[1]["headline"] == "C"
