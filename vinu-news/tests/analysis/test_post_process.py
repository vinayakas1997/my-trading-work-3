"""Tests for full post-processing pipeline."""

from vinu_news.analysis.pipeline import process_batch


def _raw(headline: str, link: str, tier: int = 2, source: str = "REUTERS") -> dict:
    return {
        "headline": headline,
        "summary": headline,
        "link": link,
        "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
        "source": source,
        "region": "US",
        "tier": tier,
    }


def test_duplicate_cluster_drops_one():
    raw_list = [
        _raw("Fed raises interest rates by 25 basis points", "https://ex.com/a"),
        _raw("Federal Reserve raises interest rates 25 bps", "https://ex.com/b"),
        _raw("Oil prices surge on supply concerns", "https://ex.com/c"),
    ]
    result = process_batch(raw_list)
    assert result.enriched_count == 3
    assert len(result.articles) == 2
    assert result.duplicates_dropped == 1
    assert result.clusters_found == 2


def test_skip_post_process_keeps_all():
    raw_list = [
        _raw("Fed raises interest rates", "https://ex.com/x"),
        _raw("Fed raises interest rates again", "https://ex.com/y"),
    ]
    result = process_batch(raw_list, skip_post_process=True)
    assert len(result.articles) == 2
    assert result.post_process_applied is False
