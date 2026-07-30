from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.server.app import create_app
from vinu_research.service import ResearchService


@pytest.fixture
def service(storage):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig()
    svc = ResearchService(config=cfg, storage=storage)
    return svc


@pytest.fixture
def app(service):
    return create_app(service)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/research/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "vinu-research"
        assert data["version"] == "0.1.0"

    def test_health_has_deps(self, client):
        resp = client.get("/research/health")
        data = resp.json()
        assert "dependencies" in data


class TestSettings:
    def test_settings_returns_config(self, client):
        resp = client.get("/research/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "features_api_url" in data
        assert "simulator_api_url" in data
        assert "max_iterations" in data


class TestRunResearch:
    def test_run_research_dry_run(self, client):
        resp = client.post(
            "/research/run",
            json={
                "user_idea": "test strategy",
                "symbol": "AAPL",
                "from_date": "2024-01-01",
                "to_date": "2024-12-31",
                "dry_run": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == -1


class TestListRuns:
    def test_list_empty(self, client):
        resp = client.get("/research/runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_insert(self, client, storage, sample_record):
        storage.insert_run(sample_record)
        resp = client.get("/research/runs")
        data = resp.json()
        assert len(data) == 1


class TestGetRun:
    def test_get_missing(self, client):
        resp = client.get("/research/runs/99999")
        assert resp.status_code == 404

    def test_get_existing(self, client, storage, sample_record):
        r = storage.insert_run(sample_record)
        resp = client.get(f"/research/runs/{r.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == r.id


class TestDeleteRun:
    def test_delete_missing(self, client):
        resp = client.delete("/research/runs/99999")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is False

    def test_delete_existing(self, client, storage, sample_record):
        r = storage.insert_run(sample_record)
        resp = client.delete(f"/research/runs/{r.id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
