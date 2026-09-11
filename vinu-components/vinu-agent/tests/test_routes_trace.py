"""GET /agent/trace/{ref_id} -- the traceability resolver (2026-09-11):
given any one reference id (session id, artifact id, order id, ...),
aggregate matches from the audit log, team_runs, strategy_store, and the
paper-performance store into one response. Each source is independently
best-effort; see server/routes_trace.py's own docstring for why.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vinu_agent.server.routes_trace as routes_trace
from vinu_agent.storage.team_runs import TeamRunStore


class _FakeArtifact:
    def __init__(self, artifact_id: str) -> None:
        self.artifact_id = artifact_id
        self.type = "strategy"
        self.name = "AAPL momentum"
        self.status = SimpleNamespace(value="ACTIVE")
        self.created_at = "2026-09-01T00:00:00+00:00"
        self.updated_at = "2026-09-10T00:00:00+00:00"
        self.source_run_id = 7
        self.initial_sharpe = 1.2
        self.deflated_sharpe = 0.9


class _FakeStrategyStore:
    def __init__(self, artifacts: dict) -> None:
        self._artifacts = artifacts

    def get_artifact(self, artifact_id: str):
        return self._artifacts.get(artifact_id)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from vinu_agent.broker.kill_switch import AuditLogger

    monkeypatch.setattr(AuditLogger, "LOG_PATH", tmp_path / "trade_audit.log")

    team_run_store = TeamRunStore(tmp_path / "team_runs.db")
    strategy_store = _FakeStrategyStore({"art_1": _FakeArtifact("art_1")})
    svc = SimpleNamespace(team_run_store=team_run_store, strategy_store=strategy_store)
    routes_trace._get_service = lambda: svc

    app = FastAPI()
    app.include_router(routes_trace.router)
    yield TestClient(app), team_run_store, AuditLogger
    routes_trace._get_service = lambda: None


class TestTraceRoute:
    def test_unknown_ref_id_returns_found_false_not_404(self, client) -> None:
        c, _, _ = client
        resp = c.get("/trace/does-not-exist")
        assert resp.status_code == 200
        body = resp.json()
        assert body["found"] is False
        assert body["audit_entries"] == []
        assert body["team_runs"] == []
        assert body["artifact"] is None

    def test_finds_audit_entries_by_session_id(self, client) -> None:
        c, _, AuditLogger = client
        AuditLogger.log("order_placed", {"order_id": "ord-1"}, session_id="sess-1", symbol="AAPL")

        resp = c.get("/trace/sess-1")
        body = resp.json()
        assert body["found"] is True
        assert len(body["audit_entries"]) == 1
        assert body["audit_entries"][0]["session_id"] == "sess-1"

    def test_finds_team_runs_by_session_id_and_artifact_id(self, client) -> None:
        c, store, _ = client
        run = store.create_run("research", triggered_by_session_id="sess-2", related_artifact_id="art_1")

        by_session = c.get("/trace/sess-2").json()
        assert [r["run_id"] for r in by_session["team_runs"]] == [run.run_id]

        by_artifact = c.get("/trace/art_1").json()
        assert [r["run_id"] for r in by_artifact["team_runs"]] == [run.run_id]

    def test_team_runs_found_by_both_are_not_duplicated(self, client) -> None:
        c, store, _ = client
        # A run whose OWN triggering session_id happens to equal its own
        # related_artifact_id would otherwise show up twice.
        run = store.create_run("research", triggered_by_session_id="shared-id", related_artifact_id="shared-id")

        body = c.get("/trace/shared-id").json()
        assert [r["run_id"] for r in body["team_runs"]] == [run.run_id]

    def test_finds_artifact(self, client) -> None:
        c, _, _ = client
        body = c.get("/trace/art_1").json()
        assert body["artifact"]["artifact_id"] == "art_1"
        assert body["artifact"]["status"] == "ACTIVE"

    def test_finds_performance(self, client) -> None:
        c, _, _ = client
        with patch("vinu_agent.broker.performance_store.get_store") as mock_get_store:
            store = mock_get_store.return_value
            store.get_meta.return_value = {"paper_days": 6}
            store.get_daily_returns.return_value = [0.01, -0.02]
            body = c.get("/trace/art_perf").json()

        assert body["performance"] == {"meta": {"paper_days": 6}, "daily_returns": [0.01, -0.02]}

    def test_one_source_raising_does_not_break_the_others(self, client) -> None:
        c, store, AuditLogger = client
        store.create_run("research", triggered_by_session_id="sess-3")
        with patch("vinu_agent.broker.kill_switch.AuditLogger.search", side_effect=RuntimeError("boom")):
            resp = c.get("/trace/sess-3")

        assert resp.status_code == 200
        body = resp.json()
        assert body["audit_entries"] == []
        assert len(body["team_runs"]) == 1

    def test_no_service_configured_degrades_to_audit_only(self, tmp_path, monkeypatch) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        monkeypatch.setattr(AuditLogger, "LOG_PATH", tmp_path / "trade_audit.log")
        AuditLogger.log("order_placed", {}, session_id="sess-orphan")
        routes_trace._get_service = lambda: None

        app = FastAPI()
        app.include_router(routes_trace.router)
        resp = TestClient(app).get("/trace/sess-orphan")

        assert resp.status_code == 200
        assert resp.json()["found"] is True
        assert resp.json()["team_runs"] == []
