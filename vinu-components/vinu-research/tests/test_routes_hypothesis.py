from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import vinu_research.hypothesis_registry as hr
from vinu_research.server.app import create_app


@pytest.fixture
def client(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "hyp.json"
    monkeypatch.setattr(hr, "HYPOTHESES_PATH", tmp)
    from unittest.mock import MagicMock
    svc = MagicMock()
    app = create_app(service=svc)
    return TestClient(app)


class TestCreateHypothesis:
    def test_creates_and_returns_id(self, client) -> None:
        resp = client.post("/research/hypotheses", json={
            "title": "SMA200 needs a wider window",
            "thesis": "The coarse pass window is too narrow to show sensitivity for a 200-period average",
            "universe": ["AAPL"],
            "strategy_type": "moving_average_crossover",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hypothesis_id"].startswith("hyp_")
        assert data["title"] == "SMA200 needs a wider window"
        assert data["universe"] == ["AAPL"]
        assert data["strategy_type"] == "moving_average_crossover"
        assert data["evidence_count"] == 0

    def test_requires_title_and_thesis(self, client) -> None:
        resp = client.post("/research/hypotheses", json={"title": "", "thesis": "x"})
        assert resp.status_code == 422


class TestAddEvidence:
    def test_adds_evidence_to_existing_hypothesis(self, client) -> None:
        create_resp = client.post("/research/hypotheses", json={
            "title": "t", "thesis": "th", "universe": ["AAPL"],
        })
        hyp_id = create_resp.json()["hypothesis_id"]

        ev_resp = client.post(f"/research/hypotheses/{hyp_id}/evidence", json={
            "metric": "sharpe",
            "value": 1.2,
            "conclusion": "supports",
            "reasoning": "widened window revealed a clear peak",
        })
        assert ev_resp.status_code == 200
        data = ev_resp.json()
        assert data["evidence_count"] == 1
        assert data["best_sharpe"] == 1.2

    def test_404_on_unknown_hypothesis(self, client) -> None:
        resp = client.post("/research/hypotheses/hyp_doesnotexist/evidence", json={
            "metric": "sharpe", "value": 1.0, "conclusion": "supports",
        })
        assert resp.status_code == 404
