"""Tests for the /v1/stage1/vinu-news/* positional API (routes_v1.py)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle, TickerMention
from vinu_news.server.app import create_app
from vinu_news.service import NewsService
from vinu_news.storage.sqlite_backend import SqliteBackend

BASE_TS = 1_700_000_000


def _insert(backend: SqliteBackend, *, link: str, headline: str, source: str, sort_ts: int, ticker: str = "AAPL") -> None:
    article = ArticleRecord(
        id=link,
        headline=headline,
        summary="",
        source=source,
        link=link,
        sort_ts=sort_ts,
        region="US",
        tier=1,
        category="MARKETS",
        priority="NORMAL",
        sentiment="NEUTRAL",
        sentiment_score=0,
        impact="LOW",
        tickers=f'["{ticker}"]',
        lang="en",
        threat_level="NONE",
        threat_cat="",
        threat_conf=0.0,
        source_flag=0,
        is_lead=1,
    )
    mention = TickerMention(id=f"{link}:{ticker}", article_id=link, ticker=ticker, dominance=1.0, is_primary=1)
    backend.persist_leads([EnrichedArticle(article=article, mentions=[mention])])


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "api_v1.db"
    storage = SqliteBackend(db)
    _insert(storage, link="https://a/1", headline="Apple reports record quarterly revenue growth surge", source="AP", sort_ts=BASE_TS)
    _insert(storage, link="https://a/2", headline="Apple reports record quarterly revenue growth surge today", source="REUTERS", sort_ts=BASE_TS + 60)
    _insert(storage, link="https://a/3", headline="Apple reports record quarterly revenue growth surge again", source="BLOOMBERG", sort_ts=BASE_TS + 120)
    _insert(storage, link="https://a/4", headline="Apple recalls devices over battery defect issue", source="CNBC", sort_ts=BASE_TS + 180)

    service = NewsService(storage=storage)
    app = create_app(service=service)
    with TestClient(app) as test_client:
        yield test_client
    service.close()


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _range() -> str:
    return f"{_iso(BASE_TS - 3600)}_{_iso(BASE_TS + 3600)}"


def test_fetch_unknown_method_is_422(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-news/fetch/AAPL/1hr/{_range()}/not-a-real-method")
    assert resp.status_code == 422


def test_fetch_bad_granularity_is_422(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-news/fetch/AAPL/2min/{_range()}/vader-finance-tuned-sentiment")
    assert resp.status_code == 422


def test_fetch_no_articles_is_404(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-news/fetch/TSLA/1hr/{_range()}/vader-finance-tuned-sentiment")
    assert resp.status_code == 404
    assert resp.json()["status"] == "not_found"


@pytest.mark.parametrize(
    "method",
    [
        "event-type-classification",
        "named-entity-recognition",
        "velocity-spike-anomaly-detection",
        "multi-source-triangulation",
        "tfidf-semantic-clustering",
        "vader-finance-tuned-sentiment",
        "llm-sentiment-classifier-alternatives",
        "structured-event-tuple-embeddings",
        "news-embedding-regime-detection",
    ],
)
def test_fetch_runs_every_method_successfully(client: TestClient, method: str) -> None:
    resp = client.get(f"/v1/stage1/vinu-news/fetch/AAPL/1hr/{_range()}/{method}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tier"] == "tier1"
    assert body["run_id"] is None
    assert body["data"] is not None


def test_fetch_multi_source_triangulation_finds_confirmed_story(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-news/fetch/AAPL/1hr/{_range()}/multi-source-triangulation")
    assert resp.status_code == 200
    signals = resp.json()["data"]
    assert len(signals) >= 1
    assert len(signals[0]["sources"]) >= 2


def test_trigger_returns_202_and_run_id(client: TestClient, monkeypatch) -> None:
    from vinu_news import service as service_module

    monkeypatch.setattr(service_module.NewsService, "run_ticker_news_ingest", lambda self, days=7: None)

    resp = client.post(f"/v1/stage1/vinu-news/trigger/AAPL/1hr/{_range()}")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "computing"
    assert body["run_id"]
