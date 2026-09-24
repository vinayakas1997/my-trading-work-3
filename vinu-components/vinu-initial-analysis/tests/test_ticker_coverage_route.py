from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vinu_initial_analysis.config import VinuInitialAnalysisConfig
from vinu_initial_analysis.server.app import create_app
from vinu_initial_analysis.service import InitialAnalysisService


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    config = VinuInitialAnalysisConfig(
        data_root=tmp_path, runs_db_path=tmp_path / "vinu_initial_analysis_runs.db"
    )
    service = InitialAnalysisService(config)
    return TestClient(create_app(service))


class TestTickerCoverageRoute:
    def test_no_runs_yet_returns_all_angles_missing(self, client: TestClient) -> None:
        resp = client.get("/analysis/coverage/AAPL")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "AAPL"
        assert body["angles_with_data"] == 0
        assert body["angle_count"] > 0
        # Every real discovered angle is present as a key, all pending
        # (models on by default, shock_personality is raw_data either way)
        assert "shock_personality" in body["angles"]
        assert body["angles"]["shock_personality"] == "pending"
        assert body["overall_status"] == "pending"

    def test_ticker_lowercased_input_normalized_uppercase(self, client: TestClient) -> None:
        resp = client.get("/analysis/coverage/aapl")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "AAPL"

    def test_reflects_a_run_recorded_through_run_log_directly(self, tmp_path: Path) -> None:
        config = VinuInitialAnalysisConfig(
            data_root=tmp_path, runs_db_path=tmp_path / "vinu_initial_analysis_runs.db"
        )
        service = InitialAnalysisService(config)
        client = TestClient(create_app(service))

        service.run_log.record_run(
            "AAPL", "shock_personality", "run-1",
            status="completed", policy_version="p1", models_enabled=True,
        )
        resp = client.get("/analysis/coverage/AAPL")
        body = resp.json()
        assert body["angles"]["shock_personality"]["status"] == "completed"
        assert body["angles_with_data"] == 1
        assert body["models_enabled"] is True
