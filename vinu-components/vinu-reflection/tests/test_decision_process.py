"""Tests for analysis D (Decision-Process / Cognition) -- the first real
reflection-layer analyst, per missing-pieces-of-system/maturity-agentic-system/
thinking-1/02-decided-pattern/05-to-do.md's recommended build order."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings

from vinu_reflection.reflection import decision_process
from vinu_agent.storage.llm_calls import LlmCallLogStore, LlmCallRecord
from vinu_agent.storage.team_runs import TeamRunStore


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed_call(llm_store: LlmCallLogStore, *, role: str, session_id: str, retry_count: int) -> None:
    llm_store.record(
        LlmCallRecord(role=role, session_id=session_id, retry_count=retry_count, tier="specialist")
    )


def _seed_run(team_store: TeamRunStore, *, session_id: str, verdict: str) -> None:
    run = team_store.create_run("some_team", triggered_by_session_id=session_id)
    team_store.mark_done(run.run_id, verdict=verdict, result_json={})


class TestDecisionProcessRun:
    def test_no_data_returns_no_findings(self, data_root):
        LlmCallLogStore(data_root / "llm_calls.db")
        TeamRunStore(data_root / "team_runs.db")
        findings = decision_process.run({"vinu_agent": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        llm_store = LlmCallLogStore(data_root / "llm_calls.db")
        team_store = TeamRunStore(data_root / "team_runs.db")
        for i in range(5):
            sid = f"sess-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=1)
            _seed_run(team_store, session_id=sid, verdict="REJECTED")

        findings = decision_process.run({"vinu_agent": data_root})
        assert findings == []

    def test_finds_role_with_higher_retry_rejection_rate(self, data_root):
        llm_store = LlmCallLogStore(data_root / "llm_calls.db")
        team_store = TeamRunStore(data_root / "team_runs.db")

        # 20 no-retry calls, all approved (PASS).
        for i in range(20):
            sid = f"norty-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=0)
            _seed_run(team_store, session_id=sid, verdict="PASS")

        # 20 retried calls, all rejected (STOP) -- a stark, real signal.
        for i in range(20):
            sid = f"rty-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=2)
            _seed_run(team_store, session_id=sid, verdict="STOP")

        findings = decision_process.run({"vinu_agent": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.analyst_name == "decision_process"
        assert finding.scope_type == "system"
        assert finding.scope_key == "orchestrator"
        assert finding.evidence_count == 40
        assert finding.primary_metric == pytest.approx(1.0)  # 100% vs 0% reject rate
        assert finding.metric_name == "retry_rejection_delta"
        assert finding.psi > 0.25  # a maximally stark shift must register as significant
        assert finding.signal_json["retry_reject_rate"] == pytest.approx(1.0)
        assert finding.signal_json["no_retry_reject_rate"] == pytest.approx(0.0)

    def test_calls_with_no_resolved_verdict_are_excluded(self, data_root):
        llm_store = LlmCallLogStore(data_root / "llm_calls.db")
        TeamRunStore(data_root / "team_runs.db")  # no runs ever created
        for i in range(40):
            _seed_call(llm_store, role="orchestrator", session_id=f"sess-{i}", retry_count=0)

        findings = decision_process.run({"vinu_agent": data_root})
        assert findings == []

    def test_two_roles_evaluated_independently(self, data_root):
        llm_store = LlmCallLogStore(data_root / "llm_calls.db")
        team_store = TeamRunStore(data_root / "team_runs.db")

        for i in range(20):
            sid = f"a-norty-{i}"
            _seed_call(llm_store, role="forecast_skill", session_id=sid, retry_count=0)
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"a-rty-{i}"
            _seed_call(llm_store, role="forecast_skill", session_id=sid, retry_count=1)
            _seed_run(team_store, session_id=sid, verdict="STOP")

        # orchestrator role never gets enough evidence.
        for i in range(5):
            sid = f"b-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=0)
            _seed_run(team_store, session_id=sid, verdict="PASS")

        findings = decision_process.run({"vinu_agent": data_root})
        assert {f.scope_key for f in findings} == {"forecast_skill"}


class TestDecisionProcessEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        llm_store = LlmCallLogStore(data_root / "llm_calls.db")
        team_store = TeamRunStore(data_root / "team_runs.db")
        reflection_store = ReflectionStore(data_root / "reflection.db")
        decision_process.seed_reference_config(reflection_store)

        for i in range(20):
            sid = f"norty-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=0)
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"rty-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=1)
            _seed_run(team_store, session_id=sid, verdict="STOP")

        findings = decision_process.run({"vinu_agent": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) == 1

        belief = reflection_store.get_belief("decision_process", "system", "orchestrator")
        assert belief is not None
        assert belief["severity"] == "significant"
        assert belief["trend"] == "stable"  # first-ever belief for this scope
