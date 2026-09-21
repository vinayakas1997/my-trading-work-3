"""Tests for routes_read.py's /analysis/angle/{angle_name}/{ticker} route
gaining a real `granularity` query param -- previously always read
AngleStorage.read()'s own hardcoded "1D" default with no way to override
it, the second of two hardcoded-to-1D spots GetAllAnglesTool
(vinu-agent) hits (see that tool's docstring for the first)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from vinu_initial_analysis.config import VinuInitialAnalysisConfig
from vinu_initial_analysis.server.app import create_app
from vinu_initial_analysis.service import InitialAnalysisService


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


def _write(service, granularity: str, value: float) -> None:
    df = pd.DataFrame([{"x": value}])
    run_id = service.storage.write("AAPL", "garch", df, tier="tier2", granularity=granularity)
    service.run_log.record_run("AAPL", "garch", run_id, row_count=len(df), granularity=granularity, tier="tier2")


def test_omitted_granularity_defaults_to_1D(client_and_service) -> None:
    client, service = client_and_service
    _write(service, "1D", 1.0)
    _write(service, "1H", 2.0)

    resp = client.get("/analysis/angle/garch/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 1
    assert body["data"][0]["x"] == 1.0  # the 1D row, not 1H -- default preserved


def test_explicit_granularity_reads_the_matching_bucket(client_and_service) -> None:
    client, service = client_and_service
    _write(service, "1D", 1.0)
    _write(service, "1H", 2.0)

    resp = client.get("/analysis/angle/garch/AAPL", params={"granularity": "1H"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 1
    assert body["data"][0]["x"] == 2.0


def test_granularity_with_no_data_returns_empty_not_the_1D_bucket(client_and_service) -> None:
    client, service = client_and_service
    _write(service, "1D", 1.0)

    resp = client.get("/analysis/angle/garch/AAPL", params={"granularity": "1W"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 0
    assert body["data"] == []
