"""Tests for the /v1/stage1/vinu-stock-price/* positional API (routes_v1.py)."""

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


def _iso(ts: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    data_root = tmp_path / "data"
    os.environ["VINU_STOCK_DATA_ROOT"] = str(data_root)

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
        "AAPL", provider="test", first_bar_ts=bars[0].bar_ts, last_bar_ts=bars[-1].bar_ts, backfill_status="complete"
    )
    service.add_watchlist_tickers(["AAPL"])

    app = create_app(service)
    yield TestClient(app)
    service.close()


def test_fetch_ok(client: TestClient) -> None:
    resp = client.get(
        "/v1/stage1/vinu-stock-price/fetch/AAPL/1min/"
        f"{_iso(0)}_{_iso(int(time.time()) + 3600)}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tier"] == "tier1"
    assert body["run_id"] is None
    assert len(body["data"]) == 10


def test_fetch_granularity_resamples(client: TestClient) -> None:
    resp = client.get(
        "/v1/stage1/vinu-stock-price/fetch/AAPL/5min/"
        f"{_iso(0)}_{_iso(int(time.time()) + 3600)}"
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


def test_fetch_not_found(client: TestClient) -> None:
    resp = client.get(
        "/v1/stage1/vinu-stock-price/fetch/NOSUCHTICKER/1min/"
        f"{_iso(0)}_{_iso(int(time.time()) + 3600)}"
    )
    assert resp.status_code == 404
    assert resp.json()["status"] == "not_found"


def test_fetch_bad_granularity(client: TestClient) -> None:
    resp = client.get(
        "/v1/stage1/vinu-stock-price/fetch/AAPL/2min/"
        f"{_iso(0)}_{_iso(int(time.time()) + 3600)}"
    )
    assert resp.status_code == 422


def test_fetch_bad_time_range(client: TestClient) -> None:
    resp = client.get("/v1/stage1/vinu-stock-price/fetch/AAPL/1min/not-a-range")
    assert resp.status_code == 422


def test_trigger_returns_run_id_and_polls(client: TestClient, monkeypatch) -> None:
    calls = []

    def _fake_run_backfill(self, symbols=None, *, from_year=None, to_year=None, dry_run=False):
        calls.append((symbols, from_year, to_year))
        from vinu_stock.service import BackfillCycleResult
        from vinu_stock.backfill.orchestrator import BackfillSummary

        return BackfillCycleResult(summary=BackfillSummary(years_ok=[from_year], years_failed=[], total_rows=0))

    monkeypatch.setattr(StockService, "run_backfill", _fake_run_backfill)

    resp = client.post(
        "/v1/stage1/vinu-stock-price/trigger/AAPL/1hr/2024-01-01T00:00:00_2024-01-02T00:00:00"
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "computing"
    run_id = body["run_id"]
    assert run_id

    deadline = time.time() + 5
    status = None
    while time.time() < deadline:
        poll = client.get(
            "/v1/stage1/vinu-stock-price/fetch/AAPL/1hr/"
            f"2024-01-01T00:00:00_2024-01-02T00:00:00/{run_id}"
        )
        status = poll.json()["status"]
        if status != "computing":
            break
        time.sleep(0.05)

    assert status in ("ok", "not_found")  # job finished either way; no real data written by the mock
    assert calls and calls[0][0] == ["AAPL"]


def test_trigger_unknown_run_id_is_404(client: TestClient) -> None:
    resp = client.get(
        "/v1/stage1/vinu-stock-price/fetch/AAPL/1hr/"
        "2024-01-01T00:00:00_2024-01-02T00:00:00/not-a-real-run-id"
    )
    assert resp.status_code == 404
