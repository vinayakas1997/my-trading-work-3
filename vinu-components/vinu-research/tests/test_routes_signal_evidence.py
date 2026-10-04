from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.server.app import create_app
from vinu_research.service import ResearchService
from vinu_research.storage.move_evidence_store import MoveEvidenceStore
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore


@pytest.fixture
def signal_evidence_store(tmp_path):
    s = SignalEvidenceStore(tmp_path / "test_signal_evidence.db")
    yield s
    s.close()


@pytest.fixture
def move_evidence_store(tmp_path):
    s = MoveEvidenceStore(tmp_path / "test_move_evidence.db")
    yield s
    s.close()


@pytest.fixture
def service(storage, strategy_store, signal_evidence_store, move_evidence_store):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig()
    return ResearchService(
        config=cfg, storage=storage, strategy_store=strategy_store,
        signal_evidence_store=signal_evidence_store,
        move_evidence_store=move_evidence_store,
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


class TestTrack2AggregateRoute:
    def test_no_evidence_on_file_returns_insufficient(self, client):
        resp = client.get(
            "/research/track2-aggregate/AAPL",
            params={"must_condition": "sma5_cross_sma50"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sample_size"] == 0
        assert body["insufficient_evidence"] is True

    def test_resolved_evidence_produces_a_confidence_number(self, client):
        client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        client.post(
            "/research/signal-evidence/t-001/outcome",
            json={"max_favorable_excursion": 0.03, "max_adverse_excursion": -0.01, "return_at_horizon": 0.02},
        )

        resp = client.get(
            "/research/track2-aggregate/AAPL",
            params={"must_condition": "sma5_cross_sma50"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sample_size"] == 1
        assert body["win_rate"] == 1.0
        assert body["evidence_confidence"] == pytest.approx((1 + 1) / (1 + 2))

    def test_as_of_query_param_is_forwarded(self, client):
        client.post("/research/signal-evidence/trigger", json=_PAYLOAD)
        client.post(
            "/research/signal-evidence/t-001/outcome",
            json={"max_favorable_excursion": 0.03, "max_adverse_excursion": -0.01, "return_at_horizon": 0.02},
        )

        resp = client.get(
            "/research/track2-aggregate/AAPL",
            params={"must_condition": "sma5_cross_sma50", "as_of": 1_600_000_000},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sample_size"] == 0  # outcome recorded well after this as_of


_MOVE_PAYLOAD = {
    "bar_ts": 1_700_000_000,
    "window_seconds": 900,
    "granularity": "15min",
    "atr": 2.0,
    "price_move": 6.0,
    "move_threshold": 4.0,
    "direction": "up",
}


class TestRecordMoveEventRoute:
    def test_records_and_lists_back(self, client):
        resp = client.post("/research/move-evidence/AAPL", json=_MOVE_PAYLOAD)
        assert resp.status_code == 200
        assert resp.json()["status"] == "recorded"

        listed = client.get("/research/move-evidence", params={"symbol": "AAPL"})
        assert listed.status_code == 200
        body = listed.json()
        assert body["count"] == 1
        assert body["events"][0]["symbol"] == "AAPL"
        assert body["events"][0]["direction"] == "up"


class TestUnconfirmedMovesRoute:
    def test_move_with_no_trigger_is_unconfirmed(self, client):
        client.post("/research/move-evidence/AAPL", json=_MOVE_PAYLOAD)

        resp = client.get("/research/unconfirmed-moves", params={"symbol": "AAPL"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["events"][0]["confirmed_by_track1"] is False

    def test_move_with_a_matching_trigger_is_confirmed_and_excluded(self, client):
        client.post("/research/move-evidence/AAPL", json=_MOVE_PAYLOAD)
        client.post(
            "/research/signal-evidence/trigger",
            json={**_PAYLOAD, "trigger_time": "2023-11-14T22:13:25+00:00"},
        )

        resp = client.get("/research/unconfirmed-moves", params={"symbol": "AAPL"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestUnconfirmedMovesContract:
    def test_answers_match_the_edge_contract(self, client):
        from vinu_infra.edge_contracts import check_payload

        edge = "research.unconfirmed_moves->agent.live_decision_context"
        assert check_payload(edge, client.get("/research/unconfirmed-moves", params={"symbol": "AAPL"}).json()) == []
        client.post("/research/move-evidence/AAPL", json=_MOVE_PAYLOAD)
        assert check_payload(edge, client.get("/research/unconfirmed-moves", params={"symbol": "AAPL"}).json()) == []


class TestSignalEvidenceListContract:
    def test_the_list_answer_matches_the_edge_contract(self, client):
        """Layer B (producer side) for the live poller's outcome resolver."""
        from vinu_infra.edge_contracts import check_payload

        edge = "research.unresolved_triggers->live.poller"
        assert check_payload(edge, client.get("/research/signal-evidence", params={"symbol": "AAPL"}).json()) == []
        client.post("/research/signal-evidence/trigger", json={
            "trigger_id": "t-contract", "symbol": "AAPL", "trigger_time": "2026-10-04T14:00:00+00:00",
            "must_condition": ["live_indicators.adx_14_gt_20"], "indicators": {"adx_14": 25.0}, "granularity": "15m",
        })
        body = client.get("/research/signal-evidence", params={"symbol": "AAPL"}).json()
        assert body["count"] == 1 and body["triggers"][0]["granularity"] == "15m"
        assert body["triggers"][0]["outcome_recorded_at"] is None
        assert check_payload(edge, body) == []
