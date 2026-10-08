"""Layer 3 of the news plan: reports of the same story from different sources are one story with tags.

Before this, a later report of a story was dropped (across polls) or discarded (inside a poll), so the sources that told it and
when each first did were lost, and `n_sources` could not exist."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vinu_news.analysis.pipeline import process_batch
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.analysis.storage.repository import NewsRepository
from vinu_news.analysis.storage.stories import story_tags

T0 = 1_800_000_000
HEAD_A = "Apple (AAPL) reports record quarterly revenue on strong iPhone sales"
HEAD_B = "Apple AAPL posts record quarterly revenue as iPhone sales climb"
HEAD_OTHER = "Tesla (TSLA) recalls vehicles over software fault"


def _raw(headline: str, source: str, link: str, pub: str = "Sun, 14 Jun 2026 12:00:00 GMT") -> dict:
    return {"headline": headline, "summary": headline, "link": link, "pubDate": pub, "source": source,
            "region": "US", "tier": 2}


@pytest.fixture
def repo(tmp_path: Path):
    r = NewsRepository(tmp_path / "l3.db")
    yield r
    r.close()


def _batch(repo, raws, seen_at):
    res = process_batch(raws)
    for item in res.articles + (res.duplicates or []):
        item.article.ingested_at = item.article.first_seen_at = item.article.last_seen_at = seen_at
    return res, persist_leads(repo, res.articles, res.duplicates)


def _story(repo, thread_id):
    return dict(repo.conn.execute("SELECT * FROM story_threads WHERE thread_id = ?", (thread_id,)).fetchone())


def test_a_later_report_from_another_source_joins_the_story_and_is_kept_as_a_raw_row(repo):
    res1, _ = _batch(repo, [_raw(HEAD_A, "REUTERS", "https://r.com/a")], T0)
    tid = res1.articles[0].article.thread_id
    _, p2 = _batch(repo, [_raw(HEAD_B, "CNBC", "https://c.com/b")], T0 + 600)
    assert p2.inserted == 0 and p2.stories_joined == 1
    story = _story(repo, tid)
    assert story["n_sources"] == 2 and story["first_source"] == "REUTERS" and story["article_count"] == 2
    sources = json.loads(story["sources_json"])
    assert [s["source"] for s in sources] == ["REUTERS", "CNBC"] and sources[1]["first_seen_at"] == T0 + 600
    rows = repo.conn.execute("SELECT source, is_lead FROM articles ORDER BY first_seen_at").fetchall()
    assert [(r["source"], r["is_lead"]) for r in rows] == [("REUTERS", 1), ("CNBC", 0)]      # both raw rows exist


def test_readers_get_one_article_per_story_with_the_tags_and_the_thread_shows_every_report(repo):
    res1, _ = _batch(repo, [_raw(HEAD_A, "REUTERS", "https://r.com/a")], T0)
    tid = res1.articles[0].article.thread_id
    _batch(repo, [_raw(HEAD_B, "CNBC", "https://c.com/b")], T0 + 600)
    served = repo.get_news_for_ticker("AAPL")
    assert [r["source"] for r in served] == ["REUTERS"]                 # not counted twice
    assert [r["source"] for r in repo.get_thread_articles(tid)] == ["CNBC", "REUTERS"] or \
        {r["source"] for r in repo.get_thread_articles(tid)} == {"REUTERS", "CNBC"}
    assert len(repo.search_articles("revenue")) == 1
    tags = story_tags(repo.conn, [tid])[tid]
    assert tags["story_n_sources"] == 2 and tags["story_sources"] == ["REUTERS", "CNBC"]
    assert tags["story_first_source"] == "REUTERS" and tags["story_n_reports"] == 2


def test_two_sources_in_the_same_poll_become_one_story_and_both_are_kept(repo):
    res, p = _batch(repo, [_raw(HEAD_A, "REUTERS", "https://r.com/a"), _raw(HEAD_B, "CNBC", "https://c.com/b"),
                           _raw(HEAD_OTHER, "REUTERS", "https://r.com/t")], T0)
    assert len(res.articles) == 2 and len(res.duplicates) == 1          # two stories, one extra report
    assert p.members_stored == 1
    aapl = next(l for l in res.articles if "Apple" in l.article.headline)
    story = _story(repo, aapl.article.thread_id)
    assert story["n_sources"] == 2 and story["article_count"] == 2
    assert repo.conn.execute("SELECT COUNT(*) FROM articles WHERE thread_id = ?", (aapl.article.thread_id,)).fetchone()[0] == 2


def test_the_same_source_again_does_not_add_a_source(repo):
    res1, _ = _batch(repo, [_raw(HEAD_A, "REUTERS", "https://r.com/a")], T0)
    _batch(repo, [_raw(HEAD_B, "REUTERS", "https://r.com/b")], T0 + 300)
    story = _story(repo, res1.articles[0].article.thread_id)
    assert story["n_sources"] == 1 and story["article_count"] == 2


def test_an_unrelated_story_is_not_merged(repo):
    res1, _ = _batch(repo, [_raw(HEAD_A, "REUTERS", "https://r.com/a")], T0)
    res2, _ = _batch(repo, [_raw(HEAD_OTHER, "CNBC", "https://c.com/t")], T0 + 60)
    assert res2.articles[0].article.thread_id != res1.articles[0].article.thread_id


def test_reports_whose_lead_was_not_stored_are_not_stored(repo):
    res = process_batch([_raw(HEAD_A, "REUTERS", "https://r.com/a"), _raw(HEAD_B, "CNBC", "https://c.com/b")])
    persisted = persist_leads(repo, [], res.duplicates)               # the lead was filtered out (watchlist mode)
    assert persisted.members_stored == 0
    assert repo.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0


def test_stories_from_before_layer_3_get_their_source(tmp_path: Path):
    path = tmp_path / "old.db"
    r = NewsRepository(path)
    res, _ = _batch(r, [_raw(HEAD_A, "REUTERS", "https://r.com/a")], T0)
    tid = res.articles[0].article.thread_id
    for col in ("sources_json", "n_sources", "first_source"):
        r.conn.execute(f"ALTER TABLE story_threads DROP COLUMN {col}")
    r.conn.commit()
    r.close()
    again = NewsRepository(path)
    try:
        story = _story(again, tid)
        assert story["n_sources"] == 1 and story["first_source"] == "REUTERS"
        assert json.loads(story["sources_json"])[0]["source"] == "REUTERS"
    finally:
        again.close()
