"""Tests for feed health tracking."""

import tempfile
from pathlib import Path

from vinu_news.rss.fetch.fetch_result import FeedPollResult
from vinu_news.rss.storage.feed_health import update_feed_health
from vinu_news.analysis.storage.repository import NewsRepository


def test_feed_health_success_and_failure():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        repo = NewsRepository(db_path)
        try:
            ok = FeedPollResult(
                feed_id="test_ok",
                url="https://example.com/ok",
                status_code=200,
                articles=[{"headline": "x", "link": "https://ex.com/x"}],
                error=None,
                duration_ms=100,
            )
            bad = FeedPollResult(
                feed_id="test_bad",
                url="https://example.com/bad",
                status_code=None,
                articles=[],
                error="timeout",
                duration_ms=4000,
            )
            update_feed_health(repo, [ok, bad])

            ok_row = repo.conn.execute(
                "SELECT * FROM feed_health WHERE feed_id = ?", ("test_ok",)
            ).fetchone()
            bad_row = repo.conn.execute(
                "SELECT * FROM feed_health WHERE feed_id = ?", ("test_bad",)
            ).fetchone()
            assert ok_row["fail_streak"] == 0
            assert ok_row["total_polls"] == 1
            assert bad_row["fail_streak"] == 1
            assert bad_row["last_error"] == "timeout"
        finally:
            repo.close()
