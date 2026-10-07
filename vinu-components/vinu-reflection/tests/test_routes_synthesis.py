"""Step 9's HTTP surface (system-wide-audit-and-design/00-overview.md,
02-open-questions-strategy-and-simulation.md): the brain's already-
durable synthesis output, read over HTTP since every intended consumer
is already a dependency of this package (a reverse in-process import
would be circular)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    ReflectionStore,
    write_finding,
)
from vinu_reflection.config import ReflectionConfig
from vinu_reflection.server.app import create_app


@pytest.fixture
def store(tmp_path):
    s = ReflectionStore(tmp_path / "reflection.db")
    yield s
    s.close()


@pytest.fixture
def config(tmp_path) -> ReflectionConfig:
    return ReflectionConfig(
        host="127.0.0.1", port=8092, data_root=tmp_path,
        agent_data_root=tmp_path, live_trade_audit_log_path=tmp_path / "log.jsonl",
        screener_data_root=tmp_path, portfolio_data_root=tmp_path,
        stock_data_root=tmp_path, initial_analysis_data_root=tmp_path,
        worker_interval_sec=300, brain_synthesis_enabled=False,
        brain_synthesis_worker_interval_sec=3600,
    )


@pytest.fixture
def client(config, store):
    app = create_app(config, store)
    return TestClient(app)


class TestGetLatestSynthesis:
    def test_no_synthesis_on_file_returns_none_status_not_404(self, client) -> None:
        resp = client.get("/reflection/synthesis/latest")
        assert resp.status_code == 200
        assert resp.json() == {"status": "none"}

    def test_returns_the_most_recently_recorded_synthesis(self, client, store) -> None:
        store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[{"belief": "x"}],
            prediction_json={"proposed_action": {"type": "narrative_only"}},
            proposed_action_type="narrative_only", resolution_criteria="n/a",
            resolve_by=time.time() + 3600, evidence_count_at_synthesis=5,
        )
        resp = client.get("/reflection/synthesis/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["synthesis"]["proposed_action_type"] == "narrative_only"

    def test_multiple_syntheses_returns_the_newest(self, client, store) -> None:
        first_id = store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={},
            proposed_action_type="narrative_only", resolution_criteria="n/a",
            resolve_by=time.time() + 3600, evidence_count_at_synthesis=1,
        )
        second_id = store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={},
            proposed_action_type="significance_flag", resolution_criteria="n/a",
            resolve_by=time.time() + 3600, evidence_count_at_synthesis=2,
        )
        resp = client.get("/reflection/synthesis/latest")
        body = resp.json()
        assert body["synthesis"]["synthesis_id"] == second_id
        assert body["synthesis"]["synthesis_id"] != first_id


class TestListPendingSyntheses:
    def test_no_pending_returns_empty(self, client) -> None:
        resp = client.get("/reflection/synthesis/pending")
        assert resp.status_code == 200
        assert resp.json() == {"syntheses": [], "count": 0}

    def test_past_resolve_by_and_unresolved_is_pending(self, client, store) -> None:
        store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={},
            proposed_action_type="threshold_nudge", resolution_criteria="n/a",
            resolve_by=time.time() - 10, evidence_count_at_synthesis=3,
        )
        resp = client.get("/reflection/synthesis/pending")
        body = resp.json()
        assert body["count"] == 1

    def test_not_yet_due_is_not_pending(self, client, store) -> None:
        store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={},
            proposed_action_type="threshold_nudge", resolution_criteria="n/a",
            resolve_by=time.time() + 3600, evidence_count_at_synthesis=3,
        )
        resp = client.get("/reflection/synthesis/pending")
        assert resp.json()["count"] == 0

    def test_resolved_is_not_pending(self, client, store) -> None:
        synthesis_id = store.record_synthesis(
            trigger_reason="scheduled", inputs_snapshot=[], prediction_json={},
            proposed_action_type="threshold_nudge", resolution_criteria="n/a",
            resolve_by=time.time() - 10, evidence_count_at_synthesis=3,
        )
        store.resolve_synthesis(synthesis_id, observed_outcome_json={"ok": True}, outcome_match="confirmed")
        resp = client.get("/reflection/synthesis/pending")
        assert resp.json()["count"] == 0


def _write_belief(store, *, psi=0.3) -> None:
    store.upsert_reference_config(
        analyst_name="regime_drift", scope_type="system", metric_name="retry_rejection_delta",
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
    )
    write_finding(store, Finding(
        analyst_name="regime_drift", cluster="Regime", scope_type="system", scope_key="market",
        signal_json={"retry_rejection_delta": 0.3}, evidence_count=40, primary_metric=0.3,
        metric_name="retry_rejection_delta", psi=psi,
    ))


class TestListNotableBeliefs:
    """A6 fix: advisory consumers read the brain's notable-belief set
    over HTTP instead of importing this package in-process."""

    def test_empty_store_returns_empty_not_404(self, client) -> None:
        resp = client.get("/reflection/beliefs/notable")
        assert resp.status_code == 200
        assert resp.json() == {"beliefs": [], "count": 0}

    def test_routine_beliefs_never_written_never_listed(self, client, store) -> None:
        _write_belief(store, psi=0.02)  # routine -> write_finding stores nothing
        resp = client.get("/reflection/beliefs/notable")
        assert resp.json()["count"] == 0

    def test_notable_belief_listed_with_its_identity(self, client, store) -> None:
        _write_belief(store, psi=0.3)
        resp = client.get("/reflection/beliefs/notable")
        body = resp.json()
        assert body["count"] == 1
        assert body["beliefs"][0]["analyst_name"] == "regime_drift"
        assert body["beliefs"][0]["severity"] in ("notable", "significant")

    def test_limit_is_respected(self, client, store) -> None:
        _write_belief(store, psi=0.3)
        resp = client.get("/reflection/beliefs/notable", params={"limit": 1})
        assert resp.json()["count"] == 1


def test_answers_match_the_edge_contracts(client, store) -> None:
    """Layer B (producer side): what the routes return validates against the contract their consumer is checked with."""
    from vinu_infra.edge_contracts import check_payload

    assert check_payload("reflection.synthesis->agent.idea_generator", client.get("/reflection/synthesis/latest").json()) == []
    assert check_payload("reflection.notable_beliefs->agent.live_decision_context", client.get("/reflection/beliefs/notable").json()) == []
    store.record_synthesis(
        trigger_reason="scheduled", inputs_snapshot=[{"belief": "x"}],
        prediction_json={"proposed_action": {"type": "narrative_only"}},
        proposed_action_type="narrative_only", resolution_criteria="n/a",
        resolve_by=time.time() + 3600, evidence_count_at_synthesis=5,
    )
    _write_belief(store, psi=0.3)
    assert check_payload("reflection.synthesis->agent.idea_generator", client.get("/reflection/synthesis/latest").json()) == []
    assert check_payload("reflection.notable_beliefs->agent.live_decision_context", client.get("/reflection/beliefs/notable").json()) == []


def test_the_service_answers_a_health_check(config, store) -> None:
    """The container had no health check, so it always showed as unchecked (problem log O15)."""
    client = TestClient(create_app(config, store))
    assert client.get("/reflection/health").status_code == 200
