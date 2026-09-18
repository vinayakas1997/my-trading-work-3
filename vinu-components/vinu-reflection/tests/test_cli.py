from __future__ import annotations

from pathlib import Path

from vinu_infra.reflection import ReflectionStore

from vinu_agent.storage.llm_calls import LlmCallLogStore, LlmCallRecord
from vinu_agent.storage.team_runs import TeamRunStore
from vinu_reflection.cli import run_cycle


def _seed_call(llm_store: LlmCallLogStore, *, role: str, session_id: str, retry_count: int) -> None:
    llm_store.record(
        LlmCallRecord(role=role, session_id=session_id, retry_count=retry_count, tier="specialist")
    )


def _seed_run(team_store: TeamRunStore, *, session_id: str, verdict: str) -> None:
    run = team_store.create_run("some_team", triggered_by_session_id=session_id)
    team_store.mark_done(run.run_id, verdict=verdict, result_json={})


class TestRunCycle:
    def test_no_data_writes_nothing(self, tmp_path):
        agent_data = tmp_path / "agent-data"
        agent_data.mkdir()
        LlmCallLogStore(agent_data / "llm_calls.db")
        TeamRunStore(agent_data / "team_runs.db")
        reflection_store = ReflectionStore(tmp_path / "reflection.db")

        written = run_cycle(reflection_store, {"vinu_agent": agent_data})
        assert written == 0

    def test_writes_significant_finding_from_real_data(self, tmp_path):
        agent_data = tmp_path / "agent-data"
        agent_data.mkdir()
        llm_store = LlmCallLogStore(agent_data / "llm_calls.db")
        team_store = TeamRunStore(agent_data / "team_runs.db")
        reflection_store = ReflectionStore(tmp_path / "reflection.db")

        for i in range(20):
            sid = f"norty-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=0)
            _seed_run(team_store, session_id=sid, verdict="PASS")
        for i in range(20):
            sid = f"rty-{i}"
            _seed_call(llm_store, role="orchestrator", session_id=sid, retry_count=1)
            _seed_run(team_store, session_id=sid, verdict="STOP")

        written = run_cycle(reflection_store, {"vinu_agent": agent_data})
        assert written == 1
        belief = reflection_store.get_belief("decision_process", "system", "orchestrator")
        assert belief is not None
        assert belief["severity"] == "significant"

    def test_one_analyst_failing_does_not_raise(self, tmp_path, monkeypatch):
        import vinu_reflection.cli as cli_module

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated analyst crash")

        monkeypatch.setattr(cli_module, "ANALYSTS", [_boom])
        reflection_store = ReflectionStore(tmp_path / "reflection.db")
        written = run_cycle(reflection_store, {"vinu_agent": tmp_path})
        assert written == 0  # failure isolated, no crash out of run_cycle
