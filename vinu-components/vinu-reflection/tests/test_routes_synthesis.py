"""Step 9's HTTP surface (system-wide-audit-and-design/00-overview.md,
02-open-questions-strategy-and-simulation.md): the brain's already-
durable synthesis output, read over HTTP since every intended consumer
is already a dependency of this package (a reverse in-process import
would be circular)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from vinu_infra.reflection import ReflectionStore
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
