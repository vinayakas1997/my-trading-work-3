"""Layer 2 of the news plan: the same item from the same source is one row with first/last seen; changed text is a linked revision.

Before this, a re-served item was skipped but still added one to its thread's daily counts every poll (so `ticker_daily_stats`
grew with every re-poll of an RSS feed), and a changed headline or summary on the same link was dropped without a trace."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from vinu_news.analysis.enrichment.enrich import enrich_article
from vinu_news.analysis.post_enrichment.synonyms.normalize import normalize_text
from vinu_news.analysis.storage.dedup import content_hash
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.analysis.storage.repository import NewsRepository

T0 = 1_800_000_000


def _raw(headline: str, summary: str | None = None, link: str = "https://ex.com/aapl-1") -> dict:
    return {
        "headline": headline,
        "summary": headline if summary is None else summary,
        "link": link,
        "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT",
        "source": "REUTERS",
        "region": "US",
        "tier": 2,
    }


def _lead(raw: dict, seen_at: int):
    item = enrich_article(raw)
    item.norm_text = normalize_text(f"{item.article.headline} {item.article.summary}")
    item.article.ingested_at = seen_at
    item.article.first_seen_at = item.article.last_seen_at = seen_at
    return item


@pytest.fixture
def repo(tmp_path: Path):
    r = NewsRepository(tmp_path / "l2.db")
    yield r
    r.close()


def _rows(repo, link="https://ex.com/aapl-1"):
    return [dict(r) for r in repo.conn.execute(
        "SELECT id, headline, summary, first_seen_at, last_seen_at, seen_count, revision_of, is_current, thread_id "
        "FROM articles WHERE link = ? ORDER BY first_seen_at, rowid", (link,)).fetchall()]


def test_the_same_item_again_only_moves_last_seen_and_the_count(repo):
    persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings"), T0)])
    daily_before = repo.conn.execute("SELECT SUM(article_count) FROM ticker_daily_stats").fetchone()[0]
    r2 = persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings"), T0 + 600)])
    r3 = persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings"), T0 + 1200)])
    assert (r2.inserted, r2.seen_again, r2.revisions) == (0, 1, 0) and r3.seen_again == 1
    (row,) = _rows(repo)
    assert row["first_seen_at"] == T0 and row["last_seen_at"] == T0 + 1200 and row["seen_count"] == 3
    daily_after = repo.conn.execute("SELECT SUM(article_count) FROM ticker_daily_stats").fetchone()[0]
    assert daily_after == daily_before          # a re-served item is not a new article in the daily counts
    thread = repo.get_thread(row["thread_id"])
    assert thread["article_count"] == 1


def test_a_cosmetic_difference_is_still_the_same_item(repo):
    persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings", "Strong quarter."), T0)])
    res = persist_leads(repo, [_lead(_raw("APPLE  (AAPL) beats  earnings!", "strong quarter"), T0 + 60)])
    assert res.seen_again == 1 and res.revisions == 0 and len(_rows(repo)) == 1
    assert content_hash("A  b", "C") == content_hash("a B", "c.")


def test_changed_text_becomes_a_linked_revision_with_its_own_first_seen(repo):
    persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings"), T0)])
    res = persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings, raises guidance"), T0 + 900)])
    assert (res.inserted, res.revisions, res.seen_again) == (0, 1, 0)
    old, new = _rows(repo)
    assert old["is_current"] == 0 and new["is_current"] == 1
    assert new["revision_of"] == old["id"] and new["first_seen_at"] == T0 + 900
    assert old["first_seen_at"] == T0                    # the first wording keeps the time we first knew it
    assert new["thread_id"] == old["thread_id"]
    # the revision is itself de-duplicated on the next poll
    again = persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings, raises guidance"), T0 + 1800)])
    assert again.seen_again == 1 and again.revisions == 0
    assert _rows(repo)[1]["seen_count"] == 2


def test_a_summary_only_change_is_not_swallowed_by_an_id_collision(repo):
    persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings", "Short."), T0)])
    res = persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings", "Short. Raises guidance."), T0 + 60)])
    assert res.revisions == 1
    old, new = _rows(repo)
    assert old["id"] != new["id"] and new["revision_of"] == old["id"]
    mentions = repo.conn.execute("SELECT article_id FROM article_ticker_mentions WHERE ticker = 'AAPL'").fetchall()
    assert {m[0] for m in mentions} == {old["id"], new["id"]}      # the revision has its own ticker mentions


def test_reads_serve_only_the_current_revision(repo):
    persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings"), T0)])
    persist_leads(repo, [_lead(_raw("Apple (AAPL) beats earnings, raises guidance"), T0 + 900)])
    old, new = _rows(repo)
    by_ticker = [r["id"] for r in repo.get_news_for_ticker("AAPL")]
    assert by_ticker == [new["id"]]
    assert [r["id"] for r in repo.get_thread_articles(new["thread_id"])] == [new["id"]]
    assert [r["id"] for r in repo.search_articles("earnings")] == [new["id"]]
    assert [r["id"] for r in repo.get_high_impact(0)] in ([], [new["id"]])


def test_rows_from_before_layer_2_get_first_seen_and_a_hash(tmp_path: Path):
    path = tmp_path / "old.db"
    repo = NewsRepository(path)
    repo.conn.execute("ALTER TABLE articles DROP COLUMN content_hash")
    for col in ("first_seen_at", "last_seen_at", "seen_count", "revision_of", "is_current"):
        repo.conn.execute(f"ALTER TABLE articles DROP COLUMN {col}")
    repo.conn.execute(
        "INSERT INTO articles (id, headline, summary, source, link, sort_ts, region, tier, category, priority, sentiment, "
        "sentiment_score, impact, tickers, lang, threat_level, threat_cat, threat_conf, ingested_at) "
        "VALUES ('o1', 'Old news', 'Body', 'X', 'https://ex.com/o1', 100, 'US', 2, 'MARKETS', 'ROUTINE', 'NEUTRAL', 0, "
        "'LOW', '[]', 'en', 'INFO', 'general', 0.3, 250)"
    )
    repo.conn.commit()
    repo.close()
    reopened = NewsRepository(path)
    try:
        row = reopened.conn.execute("SELECT first_seen_at, last_seen_at, seen_count, is_current, content_hash FROM articles "
                                    "WHERE id = 'o1'").fetchone()
        assert (row["first_seen_at"], row["last_seen_at"], row["seen_count"], row["is_current"]) == (250, 250, 1, 1)
        assert row["content_hash"] == content_hash("Old news", "Body")
    finally:
        reopened.close()


def test_the_seen_counters_do_not_re_index_the_search_table(repo):
    sql = repo.conn.execute("SELECT sql FROM sqlite_master WHERE name = 'articles_fts_update'").fetchone()[0]
    assert "UPDATE OF headline, summary" in sql
