"""Tests for FastAPI HTTP routes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_news.server.app import create_app
from vinu_news.storage.sqlite_backend import SqliteBackend


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "api.db"
    storage = SqliteBackend(db)
    from vinu_news.service import NewsService

    service = NewsService(storage=storage)
    app = create_app(service=service)
    with TestClient(app) as test_client:
        yield test_client
    service.close()


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["storage"] == "sqlite"


def test_settings_roundtrip(client: TestClient):
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "ticker"

    resp = client.patch("/settings", json={"mode": "all"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "all"


def test_watchlist_api(client: TestClient):
    resp = client.post("/watchlist/tickers", json={"tickers": ["AAPL", "NVDA"]})
    assert resp.status_code == 200
    assert set(resp.json()["tickers"]) == {"AAPL", "NVDA"}

    resp = client.delete("/watchlist/tickers/AAPL")
    assert resp.status_code == 200
    assert resp.json()["tickers"] == ["NVDA"]


def test_latest_empty(client: TestClient):
    resp = client.get("/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["data"] == []


def test_search_requires_query(client: TestClient):
    resp = client.get("/search")
    assert resp.status_code == 422
