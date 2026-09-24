from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.server.app import create_app
from vinu_research.service import ResearchService
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore


@pytest.fixture
def signal_evidence_store(tmp_path):
    s = SignalEvidenceStore(tmp_path / "test_signal_evidence.db")
    yield s
    s.close()


@pytest.fixture
def service(storage, strategy_store, signal_evidence_store):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig()
    return ResearchService(
        config=cfg, storage=storage, strategy_store=strategy_store,
        signal_evidence_store=signal_evidence_store,
    )


@pytest.fixture
def app(service):
    return create_app(service)


@pytest.fixture
def client(app):
    return TestClient(app)


_PAYLOAD = {
    "trigger_id": "t-001",
    "symbol": "AAPL",
    "trigger_time": "2026-09-24T14:30:00+00:00",
    "must_condition": "sma5_cross_sma50",
    "indicators": {
        "adx": 17.8,
        "shock_personality": {"status": "ok", "gap_fill_rate": 0.6},
    },
    "granularity": "15min",
    "policy_version": "abc123",
}


class TestRecordTriggerRoute:
    def test_records_and_reads_back(self, client):
        resp = client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json() == {"trigger_id": "t-001", "status": "recorded"}

        read = client.get("/research/signal-evidence/t-001")
        assert read.status_code == 200
        body = read.json()
        assert body["symbol"] == "AAPL"
        assert body["must_condition"] == ["sma5_cross_sma50"]
        assert body["indicators"]["adx"] == 17.8
        assert body["indicators"]["shock_personality"]["gap_fill_rate"] == 0.6
        assert body["max_favorable_excursion"] is None

    def test_duplicate_trigger_id_rejected(self, client):
        client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        resp = client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        assert resp.status_code == 409

    def test_unknown_trigger_returns_404(self, client):
        resp = client.get("/research/signal-evidence/does-not-exist")
        assert resp.status_code == 404


class TestRecordEvidenceOutcomeRoute:
    def test_records_outcome_after_trigger(self, client):
        client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        resp = client.post(
            "/research/signal-evidence/t-001/outcome",
            json={"max_favorable_excursion": 0.03, "max_adverse_excursion": -0.01, "return_at_horizon": 0.02},
        )
        assert resp.status_code == 200
        read = client.get("/research/signal-evidence/t-001").json()
        assert read["return_at_horizon"] == 0.02
        assert read["outcome_recorded_at"] is not None

    def test_outcome_for_unknown_trigger_returns_404(self, client):
        resp = client.post(
            "/research/signal-evidence/does-not-exist/outcome",
            json={"max_favorable_excursion": 0.0, "max_adverse_excursion": 0.0, "return_at_horizon": 0.0},
        )
        assert resp.status_code == 404


class TestListSignalEvidenceRoute:
    def test_lists_filtered_by_symbol(self, client):
        client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        client.post(
            "/research/signal-evidence/trigger",
            json={**_PAYLOAD, "trigger_id": "t-002", "symbol": "MSFT"},
        )
        resp = client.get("/research/signal-evidence", params={"symbol": "AAPL"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["triggers"][0]["trigger_id"] == "t-001"
