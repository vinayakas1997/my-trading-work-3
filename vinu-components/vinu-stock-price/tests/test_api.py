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
    os.environ["VINU_STOCK_DATA_ROOT"] = str(data_root)

    # Seed parquet with recent timestamps aligned to 5m buckets
    now = int(time.time())
    base_ts = (now // 300) * 300 - 10 * 60
    bars = [
        BarRecord("AAPL", "test", base_ts + i * 60, 100 + i, 101 + i, 99 + i, 100 + i, 1000)
        for i in range(10)
    ]
    out = archive_year_path(data_root, "AAPL", 2024)
    parquet.write_bars(out, parquet.bars_to_table(bars))

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
    resp = client.get("/stock/health")
    assert resp.status_code == 200
    assert resp.json()["symbol_count"] >= 1


def test_candles_1m(client: TestClient) -> None:
    resp = client.get("/stock/candles/AAPL?days=30&limit=100")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 10


def test_candles_5m_aggregate(client: TestClient) -> None:
    resp = client.get("/stock/candles/AAPL?interval=5m&days=30")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_catalog(client: TestClient) -> None:
    resp = client.get("/stock/catalog/AAPL")
    assert resp.status_code == 200
    assert resp.json()["data"][0]["symbol"] == "AAPL"


def test_ui_page(client: TestClient) -> None:
    resp = client.get("/ui/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "vinu-stock-price" in resp.text


def test_health_providers(client: TestClient) -> None:
    resp = client.get("/stock/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "providers" in body
    assert isinstance(body["providers"], list)
    assert len(body["providers"]) >= 1


def test_quote_route_unconfigured_is_200_not_ok(client: TestClient) -> None:
    # how-to-make-it-live.md #13: the quote route always returns 200 -- on any
    # upstream problem (here: no Alpaca key in the test env) the body carries
    # ok:false + error, and vinu-live's spread gate fails open on that.
    resp = client.get("/stock/quote/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["ok"] is False
    assert body["error"]
    assert body["spread_bps"] == 0.0


def test_quote_route_serves_provider_payload_and_caches(client, monkeypatch) -> None:
    from vinu_stock.providers.quote import QuoteResult

    calls = {"n": 0}

    def _fake_get_quote(self, symbol: str) -> QuoteResult:
        calls["n"] += 1
        return QuoteResult(
            True, symbol.upper(), bid=149.98, ask=150.02, mid=150.0,
            spread_bps=2.6667, ts=1_700_000_000.0,
        )

    monkeypatch.setattr(
        "vinu_stock.providers.quote.AlpacaQuoteProvider.get_quote", _fake_get_quote
    )

    first = client.get("/stock/quote/AAPL").json()
    assert first["ok"] is True
    assert first["bid"] == 149.98 and first["ask"] == 150.02
    assert abs(first["spread_bps"] - 2.6667) < 1e-6

    # second call inside the 5s TTL must not hit the provider again
    client.get("/stock/quote/AAPL")
    assert calls["n"] == 1
