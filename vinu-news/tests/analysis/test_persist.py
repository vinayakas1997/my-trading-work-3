"""Tests for persist_leads with threads and snapshots."""

import tempfile
from pathlib import Path

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.analysis.storage.repository import NewsRepository


def _lead(headline: str, link: str) -> dict:
    return {
        "headline": headline,
        "summary": headline,
        "link": link,
        "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
        "source": "REUTERS",
        "region": "US",
        "tier": 2,
    }


def _prepare(item):
    item.norm_text = normalize_text(f"{item.article.headline} {item.article.summary}")
    return item


def test_persist_creates_thread_and_inserts():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        repo = NewsRepository(db_path)
        try:
            lead = _prepare(enrich_article(_lead("Apple beats earnings", "https://ex.com/aapl")))
            result = persist_leads(repo, [lead])
            assert result.inserted == 1
            assert result.threads_created == 1
            assert lead.article.thread_id is not None
            thread = repo.get_thread(lead.article.thread_id)
            assert thread is not None
            assert thread["article_count"] == 1
        finally:
            repo.close()


def test_persist_skips_duplicate_url():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        repo = NewsRepository(db_path)
        try:
            lead = _prepare(enrich_article(_lead("Apple beats earnings", "https://ex.com/aapl")))
            persist_leads(repo, [lead])
            again = _prepare(enrich_article(_lead("Apple beats earnings again", "https://ex.com/aapl")))
            result = persist_leads(repo, [again])
            assert result.url_skipped == 1
            assert result.inserted == 0
        finally:
            repo.close()


def test_persist_thread_match_skips_second_insert():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        repo = NewsRepository(db_path)
        try:
            first = _prepare(
                enrich_article(_lead("Fed raises rates 25 bps", "https://ex.com/fed1"))
            )
            second = _prepare(
                enrich_article(
                    _lead("Federal Reserve raises interest rates 25 bps", "https://ex.com/fed2")
                )
            )
            r1 = persist_leads(repo, [first])
            r2 = persist_leads(repo, [second])
            assert r1.inserted == 1
            assert r2.thread_matched_skipped == 1
            assert r2.inserted == 0
            thread_id = first.article.thread_id
            thread = repo.get_thread(thread_id)
            assert thread["article_count"] == 2
            snapshots = repo.get_thread_timeline(thread_id)
            assert len(snapshots) >= 1
            assert snapshots[0]["article_count"] >= 2
        finally:
            repo.close()
