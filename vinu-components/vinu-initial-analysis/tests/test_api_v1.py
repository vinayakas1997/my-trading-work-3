"""Tests for the /v1/stage1/vinu-initial-analysis/* positional API (routes_v1.py)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from vinu_initial_analysis.config import VinuInitialAnalysisConfig
from vinu_initial_analysis.server.app import create_app
from vinu_initial_analysis.service import InitialAnalysisService

BASE_TS = 1_700_000_000


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _range() -> str:
    return f"{_iso(BASE_TS - 3600)}_{_iso(BASE_TS + 3600)}"


@pytest.fixture
def client_and_service(tmp_path: Path):
    config = VinuInitialAnalysisConfig(
        data_root=tmp_path, runs_db_path=tmp_path / "vinu_initial_analysis_runs.db"
    )
    service = InitialAnalysisService(config)
    app = create_app(service)
    with TestClient(app) as test_client:
        yield test_client, service
    service.close()


@pytest.fixture
def client(client_and_service):
    return client_and_service[0]


def test_fetch_unknown_method_is_422(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1day/{_range()}/not-a-real-method")
    assert resp.status_code == 422


def test_fetch_bad_granularity_is_422(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/2min/{_range()}/garch")
    assert resp.status_code == 422


def test_fetch_no_stored_data_is_404(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1day/{_range()}/garch")
    assert resp.status_code == 404
    assert resp.json()["status"] == "not_found"


def test_fetch_returns_seeded_data(client_and_service) -> None:
    client, service = client_and_service
    df = pd.DataFrame([{"status": "ok", "next_period_volatility_forecast": 0.02}])
    service.storage.write("AAPL", "garch", df, run_id="seed_run_1", tier="tier2", granularity="1D")

    resp = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1day/{_range()}/garch")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["tier"] == "tier2"
    assert body["run_id"] is None
    assert body["data"][0]["next_period_volatility_forecast"] == 0.02


def test_fetch_granularity_isolation(client_and_service) -> None:
    """A run stored under 1D shouldn't surface under a 1hr fetch — the
    granularity segment is a real filter, not decorative."""
    client, service = client_and_service
    df = pd.DataFrame([{"status": "ok", "value": 1}])
    service.storage.write("AAPL", "garch", df, run_id="seed_run_2", tier="tier2", granularity="1D")

    resp = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1hr/{_range()}/garch")
    assert resp.status_code == 404


def test_trigger_and_poll_flow(client_and_service) -> None:
    client, service = client_and_service

    resp = client.post(f"/v1/stage1/vinu-initial-analysis/trigger/AAPL/1day/{_range()}/garch")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "computing"
    assert body["tier"] == "tier3"
    run_id = body["run_id"]
    assert run_id

    # Generous deadline: AngleRunner._fetch_news() tries a real HTTP call to
    # vinu-news (not running in this test) and retries transient errors with
    # backoff before giving up gracefully and returning [] — legitimate
    # existing behavior, not something to bypass, just slow.
    deadline = time.time() + 30
    status = None
    while time.time() < deadline:
        poll = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1day/{_range()}/garch/{run_id}")
        status = poll.json()["status"]
        if status != "computing":
            break
        time.sleep(0.2)

    assert status == "ok"
    assert poll.json()["run_id"] == run_id

    # The triggered (tier3) run is now the actual current record for
    # garch/1D/tier2's exact-match fetch too? No — trigger wrote tier3,
    # plain fetch (tier2 default) should NOT see it.
    plain = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1day/{_range()}/garch")
    assert plain.status_code == 404


def test_trigger_unknown_run_id_is_404(client: TestClient) -> None:
    resp = client.get(f"/v1/stage1/vinu-initial-analysis/fetch/AAPL/1day/{_range()}/garch/not-a-real-run-id")
    assert resp.status_code == 404
