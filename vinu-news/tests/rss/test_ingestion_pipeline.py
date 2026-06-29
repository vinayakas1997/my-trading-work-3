"""Integration tests for ingestion pipeline with mocked HTTP."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import requests

from vinu_news.rss.config.feed_loader import FeedConfig
from vinu_news.rss.fetch.fetch_result import FetchResult
from vinu_news.rss.orchestration.feed_poller import poll_feed
from vinu_news.rss.orchestration.ingestion_pipeline import run_ingestion
from vinu_news.analysis.storage.repository import NewsRepository

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_RSS = (FIXTURES / "sample_rss.xml").read_bytes()


def _sample_feed() -> FeedConfig:
    return FeedConfig(
        id="test_feed",
        url="https://example.com/feed",
        source="REUTERS",
        region="US",
        tier=2,
        category="MARKETS",
    )


def test_poll_feed_success_with_mock():
    fetch_result = FetchResult(
        url="https://example.com/feed",
        status_code=200,
        body=SAMPLE_RSS,
        error=None,
        duration_ms=100,
    )
    with patch(
        "vinu_news.rss.orchestration.feed_poller.fetch_url",
        return_value=fetch_result,
    ):
        result = poll_feed(_sample_feed())
    assert result.article_count == 2
    assert result.error is None


def test_poll_feed_timeout_returns_empty():
    fetch_result = FetchResult(
        url="https://example.com/feed",
        status_code=None,
        body=b"",
        error="timeout",
        duration_ms=4000,
    )
    with patch(
        "vinu_news.rss.orchestration.feed_poller.fetch_url",
        return_value=fetch_result,
    ):
        result = poll_feed(_sample_feed())
    assert result.article_count == 0
    assert result.error == "timeout"


def test_parallel_fail_soft():
    good = FeedConfig(
        id="good", url="https://good.com", source="GOOD", region="US",
        tier=2, category="MARKETS",
    )
    bad = FeedConfig(
        id="bad", url="https://bad.com", source="BAD", region="US",
        tier=2, category="MARKETS",
    )

    def mock_fetch(url: str) -> FetchResult:
        if "good" in url:
            return FetchResult(url=url, status_code=200, body=SAMPLE_RSS, error=None, duration_ms=50)
        return FetchResult(url=url, status_code=None, body=b"", error="timeout", duration_ms=4000)

    with patch(
        "vinu_news.rss.orchestration.feed_poller.fetch_url",
        side_effect=mock_fetch,
    ):
        from vinu_news.rss.fetch.parallel_fetcher import poll_all_feeds
        raw, results = poll_all_feeds([good, bad])

    assert len(raw) == 2
    assert len(results) == 2
    assert sum(1 for r in results if r.article_count == 0) == 1


def test_pipeline_inserts_to_db():
    fetch_result = FetchResult(
        url="https://example.com/feed",
        status_code=200,
        body=SAMPLE_RSS,
        error=None,
        duration_ms=100,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"

        with patch(
            "vinu_news.rss.orchestration.ingestion_pipeline.load_feeds",
            return_value=[_sample_feed()],
        ), patch(
            "vinu_news.rss.orchestration.feed_poller.fetch_url",
            return_value=fetch_result,
        ):
            summary = run_ingestion(db_path=db_path, dry_run=False)

        assert summary.raw_count == 2
        assert summary.enriched_count == 2
        assert summary.inserted == 2
        assert summary.clusters_found == 2
        assert summary.duplicates_dropped == 0
        assert summary.threads_created == 2

        repo = NewsRepository(db_path)
        try:
            rows = repo.get_news_for_ticker("AAPL")
            assert len(rows) >= 1
            threads = repo.conn.execute("SELECT COUNT(*) FROM story_threads").fetchone()[0]
            assert threads == 2
        finally:
            repo.close()


def test_http_client_timeout_handling():
    from vinu_news.rss.fetch.http_client import fetch_url

    with patch("vinu_news.rss.fetch.http_client.requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout("timed out")
        result = fetch_url("https://example.com/feed")
    assert result.error == "timeout"
    assert result.body == b""
