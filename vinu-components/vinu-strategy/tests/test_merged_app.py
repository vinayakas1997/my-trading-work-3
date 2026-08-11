"""Tests for the Group 1 fold (component-consolidation-plan.md):
vinu-strategy + vinu-simulator served from one process. Confirms both
services' real routes respond under their real, unchanged path prefixes
(/strategy/*, /simulator/*) from a single merged FastAPI app -- the thing
this fold is actually for, not just that the module imports cleanly.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_strategy.server.merged_app import create_merged_app


@pytest.fixture(autouse=True)
def _isolated_data_roots(tmp_path, monkeypatch):
    # Both services default data_root to Path.cwd()/"data" -- redirected
    # to a tempdir so this test never writes into the real repo tree, same
    # convention as every other real-store-backed test in this monorepo.
    monkeypatch.setenv("VINU_STRATEGY_DATA_ROOT", str(tmp_path / "strategy"))
    monkeypatch.setenv("VINU_SIMULATOR_DATA_ROOT", str(tmp_path / "simulator"))
    monkeypatch.setenv("VINU_STRATEGY_STRATEGIES_DIR", str(tmp_path / "strategy" / "strategies"))


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_merged_app()) as c:
        yield c


class TestMergedAppRouting:
    def test_strategy_health_responds_under_its_real_path(self, client: TestClient) -> None:
        resp = client.get("/strategy/health")
        assert resp.status_code == 200

    def test_simulator_health_responds_under_its_real_path(self, client: TestClient) -> None:
        resp = client.get("/simulator/health")
        assert resp.status_code == 200
        # Confirms it's really vinu-simulator's own HealthResponse shape,
        # not a path collision landing on vinu-strategy's.
        body = resp.json()
        assert body["service"] == "vinu-simulator"
        assert {"strategy_api_healthy", "stock_api_healthy", "features_api_healthy"} <= body.keys()

    def test_strategy_list_route_responds_under_its_real_path(self, client: TestClient) -> None:
        resp = client.get("/strategy/strategies")
        assert resp.status_code == 200
        assert resp.json() == []  # no strategy YAMLs in the isolated tmp dir

    def test_simulator_runs_route_responds_under_its_real_path(self, client: TestClient) -> None:
        resp = client.get("/simulator/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_strategy_settings_and_simulator_settings_are_distinct(self, client: TestClient) -> None:
        strategy_settings = client.get("/strategy/settings").json()
        simulator_settings = client.get("/simulator/settings").json()
        assert "strategies_dir" in strategy_settings
        assert "initial_capital" in simulator_settings
        assert "strategies_dir" not in simulator_settings

    def test_unprefixed_paths_are_not_routed(self, client: TestClient) -> None:
        # Neither side's routes should leak through without their prefix --
        # confirms the merge didn't accidentally mount either router at root.
        assert client.get("/health").status_code == 404
        assert client.get("/strategies").status_code == 404
        assert client.get("/runs").status_code == 404
