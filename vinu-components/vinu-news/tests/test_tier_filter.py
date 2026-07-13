"""Tests for RSS tier filtering (settings + fetch + read API)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_news.analysis.storage.models import ArticleRecord, EnrichedArticle
from vinu_news.rss.config.feed_loader import FeedConfig, load_feeds
from vinu_news.server.app import create_app
from vinu_news.service import NewsService
from vinu_news.settings.store import format_active_tiers, parse_active_tiers
from vinu_news.storage.sqlite_backend import SqliteBackend


@pytest.fixture
def backend(tmp_path: Path) -> SqliteBackend:
    db = tmp_path / "tier.db"
    with SqliteBackend(db) as b:
        yield b


def test_parse_active_tiers_defaults_when_empty():
    assert parse_active_tiers("") == [1, 2, 3, 4]
    assert parse_active_tiers("1,2") == [1, 2]


def test_format_active_tiers_requires_valid():
    assert format_active_tiers([1, 3, 2]) == "1,2,3"
    with pytest.raises(ValueError):
        format_active_tiers([])


def test_load_feeds_filters_by_tier(tmp_path: Path):
    feeds_yaml = tmp_path / "feeds.yaml"
    feeds_yaml.write_text(
        """
feeds:
  - id: tier1_feed
    url: https://example.com/1
    source: AP
    region: US
    tier: 1
    category: MARKETS
    enabled: true
  - id: tier3_feed
    url: https://example.com/3
    source: ZEROHEDGE
    region: US
    tier: 3
    category: MARKETS
    enabled: true
""",
        encoding="utf-8",
    )
    all_feeds = load_feeds(path=feeds_yaml)
    assert {f.id for f in all_feeds} == {"tier1_feed", "tier3_feed"}

    tier1_only = load_feeds(path=feeds_yaml, tiers=[1])
    assert [f.id for f in tier1_only] == ["tier1_feed"]


def test_settings_active_tiers_patch(backend: SqliteBackend):
    updated = backend.patch_settings(active_tiers=[1, 2])
    assert backend.get_settings().active_tiers == [1, 2]

    with pytest.raises(ValueError):
        backend.patch_settings(active_tiers=[])


def _insert_article(backend: SqliteBackend, *, link: str, tier: int, source: str) -> None:
    article = ArticleRecord(
        id=link,
        headline=f"Headline {tier}",
        summary="Summary",
        source=source,
        link=link,
        sort_ts=1_700_000_000 + tier,
        region="US",
        tier=tier,
        category="MARKETS",
        priority="NORMAL",
        sentiment="NEUTRAL",
        sentiment_score=0,
        impact="LOW",
        tickers="[]",
        lang="en",
        threat_level="NONE",
        threat_cat="",
        threat_conf=0.0,
        source_flag=0,
        is_lead=1,
    )
    enriched = EnrichedArticle(article=article, mentions=[])
    backend.persist_leads([enriched])


def test_get_latest_filters_by_tier(backend: SqliteBackend):
    _insert_article(backend, link="https://a/1", tier=1, source="AP")
    _insert_article(backend, link="https://a/3", tier=3, source="ZEROHEDGE")

    all_rows = backend.get_latest(limit=10)
    assert len(all_rows) == 2

    tier1_rows = backend.get_latest(limit=10, tiers=[1])
    assert len(tier1_rows) == 1
    assert tier1_rows[0]["tier"] == 1


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "api.db"
    storage = SqliteBackend(db)
    service = NewsService(storage=storage)
    app = create_app(service=service)
    with TestClient(app) as test_client:
        yield test_client
    service.close()


def test_api_settings_active_tiers(client: TestClient):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert resp.json()["active_tiers"] == [1, 2, 3, 4]

    resp = client.patch("/settings", json={"active_tiers": [1]})
    assert resp.status_code == 200
    assert resp.json()["active_tiers"] == [1]


def test_api_latest_tiers_query(client: TestClient, tmp_path: Path):
    storage = SqliteBackend(tmp_path / "latest.db")
    _insert_article(storage, link="https://b/1", tier=1, source="AP")
    _insert_article(storage, link="https://b/2", tier=2, source="BLOOMBERG")
    service = NewsService(storage=storage)
    app = create_app(service=service)
    with TestClient(app) as test_client:
        resp = test_client.get("/latest?tiers=1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["tier"] == 1
    service.close()
