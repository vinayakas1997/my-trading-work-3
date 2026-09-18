"""Tests for analysis L (process-mining reasoning traces)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry
from vinu_research.storage.strategy_store import SqliteStrategyStore

from vinu_agent.session.models import Attempt, Session
from vinu_agent.session.store import SessionStore
from vinu_agent.storage.team_runs import TeamRunStore

from vinu_reflection.reflection import process_mining


@pytest.fixture
def data_root(tmp_path, monkeypatch) -> Path:
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return tmp_path


def _make_session_with_attempt(
    session_store: SessionStore, *, trace_length: int
) -> str:
    session = session_store.create_session(Session())
    attempt = Attempt(session_id=session.session_id, react_trace=[{"step": i} for i in range(trace_length)])
    session_store.save_attempt(session.session_id, attempt)
    return session.session_id


def _seed_artifact_with_outcome(
    strategy_store: SqliteStrategyStore, *, artifact_id: str, quality: float, n: int = 10
) -> None:
    strategy_store.upsert_artifact(
        Artifact(artifact_id=artifact_id, type="trade_plan", name=artifact_id, universe=["AAPL"])
    )
    n_correct = round(quality * n)
    for i in range(n):
        strategy_store.append_calibration_entry(
            CalibrationEntry(
                artifact_id=artifact_id,
                forecast_direction="up",
                actual_return_pct=1.0,
                directional_correct=(i < n_correct),
            )
        )


class TestProcessMiningRun:
    def test_no_data_returns_no_findings(self, data_root):
        SessionStore(data_root / "sessions")
        TeamRunStore(data_root / "team_runs.db")
        findings = process_mining.run({"vinu_agent": data_root})
        assert findings == []

    def test_long_traces_underperform_short_ones_is_flagged(self, data_root):
        session_store = SessionStore(data_root / "sessions")
        team_store = TeamRunStore(data_root / "team_runs.db")
        strategy_store = process_mining.get_strategy_store()

        # 15 short attempts (trace_length=2) with a high-quality outcome.
        for i in range(15):
            sid = _make_session_with_attempt(session_store, trace_length=2)
            run = team_store.create_run("risk_gatekeeper", triggered_by_session_id=sid)
            artifact_id = f"short-{i}"
            _seed_artifact_with_outcome(strategy_store, artifact_id=artifact_id, quality=1.0)
            team_store.mark_done(run.run_id, verdict="PASS", result_json={})
            team_store.set_related_artifact_id(run.run_id, artifact_id)

        # 15 long attempts (trace_length=50) with a low-quality outcome.
        for i in range(15):
            sid = _make_session_with_attempt(session_store, trace_length=50)
            run = team_store.create_run("risk_gatekeeper", triggered_by_session_id=sid)
            artifact_id = f"long-{i}"
            _seed_artifact_with_outcome(strategy_store, artifact_id=artifact_id, quality=0.0)
            team_store.mark_done(run.run_id, verdict="PASS", result_json={})
            team_store.set_related_artifact_id(run.run_id, artifact_id)

        findings = process_mining.run({"vinu_agent": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_key == "risk_gatekeeper"
        assert finding.primary_metric < 0  # long-trace attempts did WORSE
        assert finding.metric_name == "trace_length_outcome_correlation"
        assert finding.psi > 0.25
        assert finding.evidence_count == 30

    def test_attempts_without_linked_artifact_are_excluded(self, data_root):
        session_store = SessionStore(data_root / "sessions")
        TeamRunStore(data_root / "team_runs.db")
        for i in range(40):
            _make_session_with_attempt(session_store, trace_length=i)

        findings = process_mining.run({"vinu_agent": data_root})
        assert findings == []
