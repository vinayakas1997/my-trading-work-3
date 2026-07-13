"""Tests for FTS5 search."""

import tempfile
from pathlib import Path

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.analysis.storage.repository import NewsRepository


def test_search_articles_after_insert():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        repo = NewsRepository(db_path)
        try:
            raw = {
                "headline": "Jerome Powell warns on inflation",
                "summary": "Fed chair comments on rates",
                "link": "https://ex.com/powell",
                "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
                "source": "REUTERS",
                "region": "US",
                "tier": 1,
            }
            lead = enrich_article(raw)
            lead.norm_text = "powell inflation rates"
            persist_leads(repo, [lead])

            hits = repo.search_articles("Powell inflation")
            assert len(hits) >= 1
            assert "Powell" in hits[0]["headline"] or "powell" in hits[0]["headline"].lower()
        finally:
            repo.close()
