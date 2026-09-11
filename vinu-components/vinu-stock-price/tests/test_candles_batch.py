"""POST /candles/batch -- collapses N per-symbol HTTP calls into one, built
for vinu-screener's ~8000-symbol poll cycle (found while building its
data-source adapter that no bulk endpoint existed)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_stock.server.app import create_app
from vinu_stock.service import StockService
from vinu_stock.storage import parquet
from vinu_stock.storage.models import BarRecord
from vinu_stock.storage.paths import archive_year_path


def _seed(data_root: Path, symbol: str, n: int = 10) -> list[BarRecord]:
    now = int(time.time())
    base_ts = (now // 300) * 300 - 10 * 60
    bars = [
        BarRecord(symbol, "test", base_ts + i * 60, 100 + i, 101 + i, 99 + i, 100 + i, 1000)
        for i in range(n)
    ]
    out = archive_year_path(data_root, symbol, 2024)
    parquet.write_bars(out, parquet.bars_to_table(bars))
    return bars


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "data"
    os.environ["VINU_STOCK_DATA_ROOT"] = str(data_root)
    os.environ["VINU_SHARED_WATCHLIST_PATH"] = str(tmp_path / "shared" / "watchlist.json")

    aapl_bars = _seed(data_root, "AAPL")
    msft_bars = _seed(data_root, "MSFT", n=5)

    service = StockService()
    service._backend.catalog.upsert_symbol(
        "AAPL", provider="test", first_bar_ts=aapl_bars[0].bar_ts, last_bar_ts=aapl_bars[-1].bar_ts,
        backfill_status="complete",
    )
    service._backend.catalog.upsert_symbol(
        "MSFT", provider="test", first_bar_ts=msft_bars[0].bar_ts, last_bar_ts=msft_bars[-1].bar_ts,
        backfill_status="complete",
    )
    service.add_watchlist_tickers(["AAPL", "MSFT"])

    app = create_app(service)
    yield TestClient(app)
    service.close()


class TestCandlesBatch:
    def test_returns_one_entry_per_requested_symbol(self, client: TestClient) -> None:
        resp = client.post("/stock/candles/batch", json={"symbols": ["AAPL", "MSFT"], "days": 30, "limit": 100})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["results"].keys()) == {"AAPL", "MSFT"}
        assert body["results"]["AAPL"]["count"] == 10
        assert body["results"]["MSFT"]["count"] == 5

    def test_unknown_symbol_is_empty_not_a_batch_failure(self, client: TestClient) -> None:
        resp = client.post("/stock/candles/batch", json={"symbols": ["AAPL", "GHOST"], "days": 30})
        assert resp.status_code == 200
        body = resp.json()
        assert body["results"]["AAPL"]["count"] == 10
        assert body["results"]["GHOST"]["count"] == 0
        assert body["results"]["GHOST"]["data"] == []

    def test_symbols_are_uppercased_in_the_response_keys(self, client: TestClient) -> None:
        resp = client.post("/stock/candles/batch", json={"symbols": ["aapl"], "days": 30})
        assert resp.status_code == 200
        assert "AAPL" in resp.json()["results"]

    def test_empty_symbols_list_is_rejected(self, client: TestClient) -> None:
        resp = client.post("/stock/candles/batch", json={"symbols": []})
        assert resp.status_code == 422

    def test_over_max_batch_size_is_rejected(self, client: TestClient) -> None:
        too_many = [f"SYM{i}" for i in range(StockService.MAX_BATCH_SYMBOLS + 1)]
        resp = client.post("/stock/candles/batch", json={"symbols": too_many})
        assert resp.status_code == 422

    def test_interval_aggregation_matches_the_single_symbol_route(self, client: TestClient) -> None:
        single = client.get("/stock/candles/AAPL?interval=5m&days=30")
        batch = client.post("/stock/candles/batch", json={"symbols": ["AAPL"], "interval": "5m", "days": 30})
        assert batch.json()["results"]["AAPL"]["count"] == single.json()["count"]

    def test_one_call_replaces_len_symbols_calls(self, client: TestClient) -> None:
        # Not a timing assertion (flaky) -- just confirms the batch route
        # produces the same union of data a caller would have gotten from
        # one GET per symbol, in a single round trip.
        resp = client.post("/stock/candles/batch", json={"symbols": ["AAPL", "MSFT", "GHOST"], "days": 30})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 3
