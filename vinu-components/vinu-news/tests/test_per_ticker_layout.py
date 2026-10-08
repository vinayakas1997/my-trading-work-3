"""One news database per ticker (the same style as the price folders).

The reasons: a bulk prefill of one new ticker must not take a write lock that live writes for the other tickers need (seen as
'database is locked' on the shared file), a migration or rebuild should touch one small file, and removing or refilling one
ticker should be a file operation. A story about two tickers is stored in both files with the same article id."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_news import service as service_module
from vinu_news.service import NewsService
from vinu_news.storage.central_seed import seed_central_from_legacy
from vinu_news.storage.sqlite_backend import SqliteBackend
from vinu_news.storage.ticker_stores import TickerStores, clean_ticker

BOTH = {"headline": "Apple (AAPL) and Microsoft (MSFT) team up on AI chips", "summary": "Apple and Microsoft announce a deal.",
        "link": "https://x.test/both", "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT", "source": "BENZINGA", "region": "US", "tier": 2}
ONLY_AAPL = {"headline": "Apple (AAPL) beats earnings estimates", "summary": "Apple beats earnings.",
             "link": "https://x.test/aapl", "pubDate": "Mon, 15 Jun 2026 12:00:00 GMT", "source": "BENZINGA", "region": "US", "tier": 2}


class FakeRegistry:
    """Stands in for the Alpaca provider: what the feed returns for each ticker."""
    feed = {"AAPL": [BOTH, ONLY_AAPL], "MSFT": [BOTH]}

    def __init__(self, *a, **k) -> None:
        pass

    def fetch_for_ticker(self, ticker, from_ts, to_ts):
        return [dict(x) for x in self.feed.get(ticker, [])], []


@pytest.fixture
def svc(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(service_module, "TickerNewsRegistry", FakeRegistry)
    stores = TickerStores(tmp_path / "tickers")
    s = NewsService(storage=SqliteBackend(tmp_path / "central.db"), stores=stores)
    s.add_watchlist_tickers(["AAPL", "MSFT"])
    s.patch_settings(mode="ticker") if hasattr(s, "patch_settings") else None
    yield s
    stores.close()
    s.close()


def test_a_ticker_symbol_cannot_escape_the_folder(tmp_path):
    stores = TickerStores(tmp_path / "t")
    for bad in ("../evil", "a/b", "", "AAPL;DROP"):
        with pytest.raises(ValueError):
            clean_ticker(bad)
    assert stores.get("brk.b").db_path.name == "BRK.B.db"
    stores.close()


def test_ingest_writes_each_ticker_into_its_own_file_with_the_same_article_id(svc, tmp_path):
    res = svc.run_ingestion_cycle(source="ticker_news", days=3650)
    assert res.inserted >= 3
    assert sorted(p.name for p in (tmp_path / "tickers").glob("*.db")) == ["AAPL.db", "MSFT.db"]
    aapl = {r["link"]: r["id"] for r in svc.store_for("AAPL").repo.conn.execute("SELECT id, link FROM articles")}
    msft = {r["link"]: r["id"] for r in svc.store_for("MSFT").repo.conn.execute("SELECT id, link FROM articles")}
    assert set(aapl) == {"https://x.test/both", "https://x.test/aapl"}
    assert set(msft) == {"https://x.test/both"}                       # nothing about AAPL only leaks into MSFT's file
    assert aapl["https://x.test/both"] == msft["https://x.test/both"]  # one article, one id, in both files


def test_ticker_reads_use_the_tickers_own_file_and_other_reads_merge_without_repeats(svc):
    svc.run_ingestion_cycle(source="ticker_news", days=3650)
    assert {r["link"] for r in svc.get_ticker_news("AAPL", days=3650)} == {"https://x.test/both", "https://x.test/aapl"}
    assert {r["link"] for r in svc.get_ticker_news("MSFT", days=3650)} == {"https://x.test/both"}
    latest = svc.get_latest(limit=50)
    assert sorted(r["link"] for r in latest) == ["https://x.test/aapl", "https://x.test/both"]   # the shared one once
    assert len(svc.search("chips", limit=10)) == 1
    stories = svc.get_ticker_stories("MSFT", limit=10)
    assert len(stories) == 1 and stories[0]["ticker"] == "MSFT"


def test_a_thread_is_found_in_whichever_file_holds_it(svc):
    svc.run_ingestion_cycle(source="ticker_news", days=3650)
    row = svc.get_ticker_news("AAPL", days=3650)[0]
    detail = svc.get_thread_detail(row["thread_id"])
    assert detail and detail["articles"]
    assert svc.get_thread_detail("no-such-thread") is None


def test_backfill_fills_only_the_tickers_own_file(svc, tmp_path):
    out = svc.run_backfill_single("AAPL")
    assert out["status"] == "completed"
    assert (tmp_path / "tickers" / "AAPL.db").exists() and not (tmp_path / "tickers" / "MSFT.db").exists()


def test_the_listing_shows_each_ticker_and_dropping_one_leaves_the_others(svc, tmp_path):
    svc.run_ingestion_cycle(source="ticker_news", days=3650)
    listing = {t["ticker"]: t for t in svc.list_ticker_stores()}
    assert listing["AAPL"]["articles"] == 2 and listing["MSFT"]["articles"] == 1
    assert svc.drop_ticker("AAPL") is True
    assert not (tmp_path / "tickers" / "AAPL.db").exists()
    assert (tmp_path / "tickers" / "MSFT.db").exists()
    assert len(svc.get_ticker_news("MSFT", days=3650)) == 1
    assert svc.get_backfill_status_for("AAPL")["status"] == "pending"
    assert svc.drop_ticker("AAPL") is False                    # nothing left to drop


def test_a_long_write_on_one_ticker_does_not_block_another(svc, tmp_path):
    """The shared file made a prefill and the live writes fight for one lock."""
    svc.run_ingestion_cycle(source="ticker_news", days=3650)
    holder = sqlite3.connect(tmp_path / "tickers" / "AAPL.db", timeout=0.2)
    holder.execute("BEGIN IMMEDIATE")                          # a bulk prefill of AAPL holding the write lock
    try:
        svc.store_for("MSFT").repo.conn.execute("UPDATE articles SET seen_count = seen_count + 1")
        svc.store_for("MSFT").repo.conn.commit()               # MSFT is not affected
        with pytest.raises(sqlite3.OperationalError):
            probe = sqlite3.connect(tmp_path / "tickers" / "AAPL.db", timeout=0.2)
            probe.execute("UPDATE articles SET seen_count = seen_count + 1")
    finally:
        holder.rollback()
        holder.close()


def test_a_fresh_start_carries_the_configuration_and_leaves_the_news_behind(tmp_path):
    legacy = SqliteBackend(tmp_path / "vinu_news.db")
    legacy.add_watchlist_tickers(["AAPL", "NVDA"])
    legacy.ensure_backfill_ticker("AAPL")
    legacy.update_backfill_progress("AAPL", backfilled_up_to_ts=1_700_000_000, article_count=500, oldest_ts=1_600_000_000)
    legacy.mark_backfill_completed("AAPL")
    legacy.repo.conn.execute(
        "INSERT INTO articles (id, headline, summary, source, link, sort_ts, region, tier, category, priority, sentiment, "
        "sentiment_score, impact, tickers, lang, threat_level, threat_cat, threat_conf) VALUES "
        "('a1','h','s','X','https://l',1,'US',2,'M','R','NEUTRAL',0,'LOW','[]','en','INFO','g',0.1)")
    legacy.repo.conn.commit()
    legacy_articles = legacy.repo.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    legacy.close()

    central = SqliteBackend(tmp_path / "news_central.db")
    counts = seed_central_from_legacy(central, tmp_path / "vinu_news.db")
    assert set(central.get_watchlist()) == {"AAPL", "NVDA"}
    status = central.get_backfill_status("AAPL")
    assert status.status == "pending" and not status.backfilled_up_to_ts and status.article_count == 0
    assert central.repo.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
    assert counts["watchlist"] == 2
    central.close()
    again = sqlite3.connect(tmp_path / "vinu_news.db")                  # the archive is untouched
    assert again.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == legacy_articles
    again.close()


def test_the_api_lists_and_drops_ticker_datasets(tmp_path, monkeypatch):
    from vinu_news.server.app import create_app

    monkeypatch.setattr(service_module, "TickerNewsRegistry", FakeRegistry)
    stores = TickerStores(tmp_path / "tickers")
    s = NewsService(storage=SqliteBackend(tmp_path / "central.db"), stores=stores)
    s.add_watchlist_tickers(["AAPL", "MSFT"])
    s.run_ingestion_cycle(source="ticker_news", days=3650)
    c = TestClient(create_app(service=s))             # no lifespan: the background indexer would hold the files open
    if True:
        body = c.get("/news/tickers").json()
        assert body["layout"] == "per_ticker" and {t["ticker"] for t in body["tickers"]} == {"AAPL", "MSFT"}
        assert c.get("/news/health").json()["layout"] == "per_ticker"
        assert c.delete("/news/tickers/AAPL").json() == {"ticker": "AAPL", "removed": True, "backfill": "pending"}
        assert c.delete("/news/tickers/..%2Fx").status_code in (400, 404, 422)
        assert c.get("/news/ticker/MSFT", params={"days": 3650}).json()["count"] == 1
    stores.close()
    s.close()
