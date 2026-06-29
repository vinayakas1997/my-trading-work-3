"""Tests for cross-batch thread matcher."""

import tempfile
from pathlib import Path

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text
from vinu_news.analysis.storage.repository import NewsRepository
from vinu_news.analysis.storage.threading.assign import thread_row_from_article
from vinu_news.analysis.storage.threading.matcher import find_matching_thread


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


def test_find_matching_thread():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        repo = NewsRepository(db_path)
        try:
            existing = enrich_article(
                _raw("Fed raises interest rates by 25 basis points", "https://ex.com/1")
            )
            existing.norm_text = normalize_text(
                f"{existing.article.headline} {existing.article.summary}"
            )
            row = thread_row_from_article(existing, "thread-fed-1")
            repo.conn.execute(
                """
                INSERT INTO story_threads (
                    thread_id, first_seen_at, last_seen_at, article_count,
                    lead_headline, dominant_ticker, entities_json, category,
                    last_article_id, norm_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["thread_id"],
                    row["first_seen_at"],
                    row["last_seen_at"],
                    row["article_count"],
                    row["lead_headline"],
                    row["dominant_ticker"],
                    row["entities_json"],
                    row["category"],
                    row["last_article_id"],
                    row["norm_text"],
                ),
            )
            repo.conn.commit()

            candidate = enrich_article(
                _raw("Federal Reserve raises interest rates 25 bps", "https://ex.com/2")
            )
            candidate.norm_text = normalize_text(
                f"{candidate.article.headline} {candidate.article.summary}"
            )
            match = find_matching_thread(
                repo, candidate, candidate.article.entities()
            )
            assert match == "thread-fed-1"
        finally:
            repo.close()
