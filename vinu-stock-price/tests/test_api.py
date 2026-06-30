"""API tests with fixture parquet data."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_stock.server.app import create_app
from vinu_stock.service import StockService
from vinu_stock.storage.models import BarRecord
from vinu_stock.storage import parquet
from vinu_stock.storage.paths import archive_year_path


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "data"
    meta_db = data_root / "meta.db"
    os.environ["VINU_STOCK_DATA_ROOT"] = str(data_root)
    os.environ["VINU_STOCK_META_DB_PATH"] = str(meta_db)

    # Seed parquet with recent timestamps aligned to 5m buckets
    now = int(time.time())
    base_ts = (now // 300) * 300 - 10 * 60
    bars = [
        BarRecord("AAPL", "test", base_ts + i * 60, 100 + i, 101 + i, 99 + i, 100 + i, 1000)
        for i in range(10)
    ]
    out = archive_year_path(data_root, "AAPL", 2024)
    parquet.write_bars(out, bars)

    service = StockService()
    service._backend.catalog.upsert_symbol(
        "AAPL",
        provider="test",
        first_bar_ts=bars[0].bar_ts,
        last_bar_ts=bars[-1].bar_ts,
        backfill_status="complete",
    )
    service.add_watchlist_tickers(["AAPL"])

    app = create_app(service)
    yield TestClient(app)
    service.close()


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["symbol_count"] >= 1


def test_candles_1m(client: TestClient) -> None:
    resp = client.get("/candles/AAPL?days=30&limit=100")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 10


def test_candles_5m_aggregate(client: TestClient) -> None:
    resp = client.get("/candles/AAPL?interval=5m&days=30")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_catalog(client: TestClient) -> None:
    resp = client.get("/catalog/AAPL")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["symbol"] == "AAPL"


def test_ui_page(client: TestClient) -> None:
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "vinu-stock-price" in resp.text


def test_health_providers(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body
    assert isinstance(body["providers"], list)
    assert len(body["providers"]) >= 1
