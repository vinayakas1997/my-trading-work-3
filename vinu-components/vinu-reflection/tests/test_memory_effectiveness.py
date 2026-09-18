"""Tests for analysis K (Decision-Process / Cognition) -- does retrieved
memory actually help. See missing-pieces-of-system/maturity-agentic-system/
thinking-1/02-decided-pattern/25-A-Y-details/04-decision-process-cognition.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings

from vinu_reflection.reflection import memory_effectiveness
from vinu_agent.storage.injected_context_log import InjectedContextLogStore
from vinu_agent.storage.team_runs import TeamRunStore


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed_run(team_store: TeamRunStore, *, session_id: str, verdict: str) -> None:
    run = team_store.create_run("some_team", triggered_by_session_id=session_id)
    team_store.mark_done(run.run_id, verdict=verdict, result_json={})


class TestMemoryEffectivenessRun:
    def test_no_data_returns_no_findings(self, data_root):
        InjectedContextLogStore(data_root / "injected_context_log.db")
        TeamRunStore(data_root / "team_runs.db")
        findings = memory_effectiveness.run({"vinu_agent": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
        team_store = TeamRunStore(data_root / "team_runs.db")
        for i in range(5):
            sid = f"sess-{i}"
            context_store.record(sid, fact_ids=["fact-1"], memory_ids=[])
            _seed_run(team_store, session_id=sid, verdict="REJECTED")

        findings = memory_effectiveness.run({"vinu_agent": data_root})
        assert findings == []

    def test_finds_facts_registry_helping(self, data_root):
        context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
        team_store = TeamRunStore(data_root / "team_runs.db")

        # 20 sessions with a fact injected, all approved (PASS).
        for i in range(20):
            sid = f"with-{i}"
            context_store.record(sid, fact_ids=["fact-1"], memory_ids=[])
            _seed_run(team_store, session_id=sid, verdict="PASS")

        # 20 sessions with nothing injected, all rejected (STOP).
        for i in range(20):
            sid = f"without-{i}"
            _seed_run(team_store, session_id=sid, verdict="STOP")

        findings = memory_effectiveness.run({"vinu_agent": data_root})
        by_scope = {f.scope_key: f for f in findings}
        assert "facts_registry" in by_scope
        finding = by_scope["facts_registry"]
        assert finding.analyst_name == "memory_effectiveness"
        assert finding.scope_type == "system"
        assert finding.evidence_count == 40
        assert finding.primary_metric == pytest.approx(1.0)  # 100% vs 0% quality
        assert finding.metric_name == "verdict_quality_delta"
        assert finding.signal_json["verdict_quality_with"] == pytest.approx(1.0)
        assert finding.signal_json["verdict_quality_without"] == pytest.approx(0.0)

    def test_sources_evaluated_independently(self, data_root):
        context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
        team_store = TeamRunStore(data_root / "team_runs.db")

        # facts_registry gets enough evidence, unified_memory never has any hits.
        for i in range(20):
            sid = f"fact-with-{i}"
            context_store.record(sid, fact_ids=["fact-1"], memory_ids=[])
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"fact-without-{i}"
            _seed_run(team_store, session_id=sid, verdict="STOP")

        findings = memory_effectiveness.run({"vinu_agent": data_root})
        assert {f.scope_key for f in findings} == {"facts_registry"}

    def test_sessions_with_no_resolved_verdict_are_excluded(self, data_root):
        context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
        TeamRunStore(data_root / "team_runs.db")  # no runs ever created
        for i in range(40):
            context_store.record(f"sess-{i}", fact_ids=["fact-1"], memory_ids=[])

        findings = memory_effectiveness.run({"vinu_agent": data_root})
        assert findings == []

    def test_memory_and_facts_can_both_fire_independently(self, data_root):
        context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
        team_store = TeamRunStore(data_root / "team_runs.db")

        for i in range(20):
            sid = f"fact-with-{i}"
            context_store.record(sid, fact_ids=["fact-1"], memory_ids=[])
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"fact-without-{i}"
            _seed_run(team_store, session_id=sid, verdict="STOP")
        for i in range(20):
            sid = f"mem-with-{i}"
            context_store.record(sid, fact_ids=[], memory_ids=["mem-1"])
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"mem-without-{i}"
            _seed_run(team_store, session_id=sid, verdict="STOP")

        findings = memory_effectiveness.run({"vinu_agent": data_root})
        assert {f.scope_key for f in findings} == {"facts_registry", "unified_memory"}


class TestMemoryEffectivenessEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        context_store = InjectedContextLogStore(data_root / "injected_context_log.db")
        team_store = TeamRunStore(data_root / "team_runs.db")
        reflection_store = ReflectionStore(data_root / "reflection.db")
        memory_effectiveness.seed_reference_config(reflection_store)

        for i in range(20):
            sid = f"with-{i}"
            context_store.record(sid, fact_ids=["fact-1"], memory_ids=[])
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"without-{i}"
            _seed_run(team_store, session_id=sid, verdict="STOP")

        findings = memory_effectiveness.run({"vinu_agent": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) == 1

        belief = reflection_store.get_belief("memory_effectiveness", "system", "facts_registry")
        assert belief is not None
        assert belief["severity"] == "significant"
