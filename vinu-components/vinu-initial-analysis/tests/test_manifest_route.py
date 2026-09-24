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


class TestManifestRoute:
    def test_returns_the_real_build_manifest_shape(self, client: TestClient) -> None:
        resp = client.get("/analysis/manifest")
        assert resp.status_code == 200
        body = resp.json()
        assert "policy_version" in body
        assert "models_enabled" in body
        assert "angle_inventory" in body
        assert body["angle_inventory"]["total"] > 0
        assert "evidence_table" in body

    def test_matches_calling_build_manifest_directly(self, client: TestClient, tmp_path: Path) -> None:
        """Not just "a 200 with some keys" -- the route's response is
        byte-for-byte what build_manifest(svc.list_angles()) itself
        returns, confirmed by calling the real function directly and
        comparing, not by re-deriving expected values by hand."""
        from vinu_infra.system_manifest import build_manifest

        config = VinuInitialAnalysisConfig(
            data_root=tmp_path, runs_db_path=tmp_path / "vinu_initial_analysis_runs.db"
        )
        service = InitialAnalysisService(config)
        expected = build_manifest(service.list_angles())

        resp = client.get("/analysis/manifest")
        assert resp.json() == expected

    def test_recomputes_fresh_on_every_call_not_cached(self, client: TestClient) -> None:
        """Confirms the "always live, no caching" decision (Decision 13)
        actually holds structurally: build_manifest() is invoked again on
        every request, not memoized after the first call. (MODELS_ENABLED
        itself is intentionally boot-only per model_policy.py's own
        docstring -- a module-level constant read once at import, not a
        runtime-toggleable value -- so "no caching" here is about the
        route/manifest layer, not about the policy flag being live-
        editable within a running process.)"""
        from unittest.mock import patch

        with patch(
            "vinu_infra.system_manifest.build_manifest", return_value={"stub": True},
        ) as mock_build:
            client.get("/analysis/manifest")
            client.get("/analysis/manifest")
        assert mock_build.call_count == 2
