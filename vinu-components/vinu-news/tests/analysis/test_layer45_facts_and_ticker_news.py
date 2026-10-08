"""Layers 4 and 5 of the news plan: facts about each story (computed once) and the one table consumers read.

Before these, a consumer had to join articles, mentions and threads itself, got no event tag, no list of other tickers, no
source count, and a sentiment label instead of a number with its method."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_news.analysis.pipeline import process_batch
from vinu_news.analysis.storage import ticker_news as tn
from vinu_news.analysis.storage.facts import compute_facts, event_tag, keywords, refresh_sentiment_from_finbert
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.analysis.storage.repository import NewsRepository

T0 = 1_800_000_000
HEAD_A = "Apple (AAPL) reports record quarterly earnings, Microsoft (MSFT) also gains"
HEAD_B = "Apple AAPL posts record quarterly earnings as iPhone sales climb"


def _raw(headline, source="REUTERS", link="https://r.com/a", summary=None, pub="Sun, 14 Jun 2026 12:00:00 GMT"):
    return {"headline": headline, "summary": summary if summary is not None else headline, "link": link,
            "pubDate": pub, "source": source, "region": "US", "tier": 2}


@pytest.fixture
def repo(tmp_path: Path):
    r = NewsRepository(tmp_path / "l45.db")
    yield r
    r.close()


def _batch(repo, raws, seen_at):
    res = process_batch(raws)
    for item in res.articles + (res.duplicates or []):
        item.article.ingested_at = item.article.first_seen_at = item.article.last_seen_at = seen_at
    persist_leads(repo, res.articles, res.duplicates)
    return res


def _rows(repo, ticker):
    return {r["story_id"]: r for r in tn.query(repo.conn, ticker)}


def test_event_tags_and_keywords():
    assert event_tag("Pfizer wins FDA approval for new drug") == "fda"
    assert event_tag("Acme to acquire Beta in $2B deal") == "m_and_a"
    assert event_tag("Apple beats earnings estimates") == "earnings"
    assert event_tag("Tesla raises full-year guidance") == "guidance"
    assert event_tag("Analyst upgrades Nvidia, lifts price target") == "analyst"
    assert event_tag("Quiet day on Wall Street") == "other"
    assert keywords("Apple record revenue, record iPhone sales, record profit")[0] == "record"


def test_a_new_story_gets_facts_and_a_row_per_ticker(repo):
    res = _batch(repo, [_raw(HEAD_A)], T0)
    tid = res.articles[0].article.thread_id
    facts = dict(repo.conn.execute("SELECT * FROM story_facts WHERE story_id = ?", (tid,)).fetchone())
    assert facts["primary_ticker"] == "AAPL" and facts["event_tag"] == "earnings"
    assert facts["sentiment_method"] == "rule_based" and isinstance(facts["sentiment_score"], float)
    assert [o["ticker"] for o in json.loads(facts["other_tickers_json"])] == ["MSFT"]
    aapl, msft = _rows(repo, "AAPL")[tid], _rows(repo, "MSFT")[tid]
    assert (aapl["role"], msft["role"]) == ("primary", "mentioned")
    assert aapl["first_seen_at"] == T0 and aapl["n_sources"] == 1 and aapl["event_tag"] == "earnings"


def test_finbert_replaces_the_number_and_says_so(repo):
    res = _batch(repo, [_raw(HEAD_A)], T0)
    lead = res.articles[0].article
    refresh_sentiment_from_finbert(repo.conn, lead.id, 0.83)
    repo.conn.commit()
    row = _rows(repo, "AAPL")[lead.thread_id]
    assert row["sentiment_score"] == 0.83 and row["sentiment_method"] == "finbert"
    facts = repo.conn.execute("SELECT sentiment_method FROM story_facts WHERE story_id = ?", (lead.thread_id,)).fetchone()
    assert facts[0] == "finbert"
    lead.finbert_score = -0.4
    from vinu_news.analysis.storage.models import EnrichedArticle
    assert compute_facts(EnrichedArticle(article=lead))["sentiment_method"] == "finbert"


def test_a_later_report_only_moves_the_counters_and_the_end_time(repo):
    res = _batch(repo, [_raw(HEAD_A)], T0)
    tid = res.articles[0].article.thread_id
    before = dict(repo.conn.execute("SELECT computed_at, keywords_json FROM story_facts WHERE story_id = ?", (tid,)).fetchone())
    _batch(repo, [_raw(HEAD_B, source="CNBC", link="https://c.com/b")], T0 + 900)
    row = _rows(repo, "AAPL")[tid]
    assert row["n_sources"] == 2 and row["n_reports"] == 2 and row["last_seen_at"] == T0 + 900
    assert row["first_seen_at"] == T0
    after = dict(repo.conn.execute("SELECT computed_at, keywords_json FROM story_facts WHERE story_id = ?", (tid,)).fetchone())
    assert after == before                                  # nothing was re-analysed
    _batch(repo, [_raw(HEAD_A)], T0 + 1800)                  # the first source serves it again
    assert _rows(repo, "AAPL")[tid]["last_seen_at"] == T0 + 1800


def test_a_changed_lead_recomputes_the_facts(repo):
    res = _batch(repo, [_raw("Apple (AAPL) news of the day", summary="Nothing much.")], T0)
    tid = res.articles[0].article.thread_id
    assert _rows(repo, "AAPL")[tid]["event_tag"] == "other"
    _batch(repo, [_raw("Apple (AAPL) news of the day", summary="Apple beats earnings estimates.")], T0 + 600)
    assert _rows(repo, "AAPL")[tid]["event_tag"] == "earnings"


def test_the_query_filters(repo):
    _batch(repo, [_raw(HEAD_A), _raw("Apple (AAPL) wins FDA approval for sensor", link="https://r.com/f",
                                     pub="Mon, 15 Jun 2026 12:00:00 GMT")], T0)
    _batch(repo, [_raw(HEAD_B, source="CNBC", link="https://c.com/b")], T0 + 60)
    all_rows = tn.query(repo.conn, "AAPL")
    assert [r["published_at"] for r in all_rows] == sorted((r["published_at"] for r in all_rows), reverse=True)
    assert {r["event_tag"] for r in tn.query(repo.conn, "AAPL", event_tag="fda")} == {"fda"}
    assert all(r["n_sources"] >= 2 for r in tn.query(repo.conn, "AAPL", min_sources=2)) and tn.query(repo.conn, "AAPL", min_sources=2)
    assert tn.query(repo.conn, "AAPL", known_by=T0 - 1) == []
    assert tn.query(repo.conn, "AAPL", to_ts=0) == []


def test_rebuild_recomputes_everything_from_the_raw_rows_and_runs_once(repo):
    _batch(repo, [_raw(HEAD_A)], T0)
    _batch(repo, [_raw(HEAD_B, source="CNBC", link="https://c.com/b")], T0 + 60)
    before = [dict(r) for r in repo.conn.execute("SELECT * FROM ticker_news ORDER BY ticker, story_id").fetchall()]
    repo.conn.execute("DELETE FROM ticker_news")
    repo.conn.execute("DELETE FROM story_facts")
    repo.conn.commit()
    assert tn.rebuild_once(repo.conn) is True
    assert tn.rebuild_once(repo.conn) is False               # once per database
    after = [dict(r) for r in repo.conn.execute("SELECT * FROM ticker_news ORDER BY ticker, story_id").fetchall()]
    strip = lambda rows: [{k: v for k, v in r.items() if k != "updated_at"} for r in rows]
    assert strip(after) == strip(before)


@pytest.fixture
def client(tmp_path: Path):
    from vinu_news.server.app import create_app
    from vinu_news.service import NewsService
    from vinu_news.storage.sqlite_backend import SqliteBackend

    storage = SqliteBackend(tmp_path / "api.db")
    _batch(storage.repo, [_raw(HEAD_A)], T0)
    service = NewsService(storage=storage)
    with TestClient(create_app(service=service)) as c:
        yield c
    service.close()


def test_the_ticker_news_route_serves_the_table(client):
    body = client.get("/news/ticker-news/AAPL").json()
    assert body["count"] == 1
    row = body["data"][0]
    assert row["role"] == "primary" and row["event_tag"] == "earnings" and row["n_sources"] == 1
    assert client.get("/news/ticker-news/MSFT").json()["data"][0]["role"] == "mentioned"
    capped = client.get("/news/ticker-news/AAPL", params={"as_of": 1, "to": 9_999_999_999})
    assert capped.headers.get("X-Clamped-To-As-Of") == "true" and capped.json()["count"] == 0
    assert client.get("/news/ticker-news/AAPL", params={"event_tag": "fda"}).json()["count"] == 0
