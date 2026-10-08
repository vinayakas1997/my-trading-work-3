"""The news read must not depend on stock-price (chain C1 of the data audit).

Every page of `/news/ticker/{symbol}` used to attach a price reaction by reading candles from stock-price: about 8 s a page,
137 s for AAPL's 7,941 articles, and a failure part-way made the analysis save an empty result. Nothing reads the reaction
(the news-price angle computes its own), so it is opt-in now."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_news.analysis.pipeline import process_batch
from vinu_news.analysis.storage.persist import persist_leads
from vinu_news.service import NewsService
from vinu_news.storage.sqlite_backend import SqliteBackend


@pytest.fixture
def service(tmp_path: Path):
    storage = SqliteBackend(tmp_path / "c1.db")
    res = process_batch([{"headline": "Apple (AAPL) beats earnings", "summary": "Apple beats earnings.",
                          "link": "https://r.com/a", "pubDate": "Sun, 14 Jun 2026 12:00:00 GMT", "source": "REUTERS",
                          "region": "US", "tier": 2}])
    persist_leads(storage.repo, res.articles, res.duplicates)
    s = NewsService(storage=storage)
    yield s
    s.close()


def test_the_default_read_never_touches_the_price_service(service, monkeypatch):
    def boom(self, rows):
        raise AssertionError("the news read called the price service")

    monkeypatch.setattr(NewsService, "_enrich_with_price_reaction", boom)
    rows = service.get_ticker_news("AAPL", days=36500)
    assert len(rows) == 1 and rows[0]["story_n_sources"] == 1
    assert "price_change_1h" not in rows[0]
    assert service.get_thread_detail(rows[0]["thread_id"])["articles"]
    assert service.get_thread_timeline(rows[0]["thread_id"]) is not None


def test_the_reaction_is_still_available_when_asked_for(service, monkeypatch):
    calls = []
    monkeypatch.setattr(NewsService, "_enrich_with_price_reaction", lambda self, rows, backend=None: calls.append(len(rows)) or rows)
    service.get_ticker_news("AAPL", days=36500, include_reaction=True)
    assert calls == [1]
