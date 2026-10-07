"""A restart kills a research run (a run takes 5 to 100 minutes), but the specialists' finished tasks are stored. The next
run for the same ticker is handed that work and counts its tested attempts toward the budget (problem log O7)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from vinu_agent.agent.team import TeamManager, resume_briefing
from vinu_agent.storage.team_runs import STATUS_FAILED, TeamRunStore
from vinu_agent.agent.tools import ToolRegistry

from tests.test_team import FakeLLM, _make_research_team_dir

SESSION = "planner-AMD"


def _interrupted_run(store: TeamRunStore, *, session: str = SESSION, tasks=(("idea_generator", "idea: RSI dip"),
                     ("backtest_runner", "sharpe -0.2, 14 trades"), ("risk_critic", "too few trades"))):
    run = store.create_run("research", triggered_by_session_id=session)
    store.mark_running(run.run_id)
    for agent, result in tasks:
        t = store.add_task(run.run_id, agent_name=agent)
        store.mark_task_running(t.task_id)
        store.mark_task_completed(t.task_id, result=result)
    store.fail_interrupted("interrupted: the agent container restarted while this run was in flight")
    return run


def test_the_briefing_lists_finished_work_and_counts_tested_attempts():
    text, attempts = resume_briefing([
        {"agent_name": "idea_generator", "result": "idea A"}, {"agent_name": "backtest_runner", "result": "sharpe 0.1"},
        {"agent_name": "backtest_runner", "result": "sharpe 0.3"},
    ])
    assert attempts == 2 and "idea A" in text and "already count toward your required attempts" in text


def test_an_empty_history_gives_no_briefing():
    assert resume_briefing([]) == ("", 0)


def test_the_store_finds_only_a_recent_unclaimed_interrupted_run_of_the_same_session(tmp_path):
    store = TeamRunStore(tmp_path / "team_runs.db")
    old = _interrupted_run(store)
    assert store.find_resumable("research", SESSION).run_id == old.run_id
    assert store.find_resumable("research", "planner-NVDA") is None            # another ticker's run is not ours
    conn = store._get_conn()
    conn.execute("UPDATE team_runs SET created_at = '2020-01-01T00:00:00Z' WHERE run_id = ?", (old.run_id,))
    conn.commit()
    assert store.find_resumable("research", SESSION) is None                    # too old to be useful
    conn.execute("UPDATE team_runs SET created_at = ? WHERE run_id = ?", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), old.run_id))
    conn.commit()
    store.mark_resumed(old.run_id, "newrun")
    assert store.find_resumable("research", SESSION) is None                    # claimed once, not twice


def test_a_run_that_failed_for_another_reason_is_not_resumed(tmp_path):
    store = TeamRunStore(tmp_path / "team_runs.db")
    run = store.create_run("research", triggered_by_session_id=SESSION)
    store.mark_failed(run.run_id, error_message="LLM call failed at iteration 0")
    assert store.find_resumable("research", SESSION) is None


def test_the_next_research_run_gets_the_earlier_work_in_its_prompt_and_is_linked(tmp_path):
    store = TeamRunStore(tmp_path / "team_runs.db")
    old = _interrupted_run(store)
    seen: list[Any] = []

    class Recording(FakeLLM):
        def chat(self, messages, tools=None):
            seen.append(messages)
            return {"content": "Verdict: STOP"}

    manager = TeamManager(_make_research_team_dir(tmp_path), full_registry=ToolRegistry(), llm=Recording(), run_store=store,
                          triggered_by_session_id=SESSION)
    result = manager.run("research AMD")
    prompt = " ".join(str(m.get("content", "")) for m in seen[0])
    assert "RSI dip" in prompt and "sharpe -0.2" in prompt
    new = store.get_run(result["run_id"])
    assert store._get_conn().execute("SELECT resumed_from FROM team_runs WHERE run_id = ?", (new.run_id,)).fetchone()[0] == old.run_id
    assert store.find_resumable("research", SESSION) is None


def test_a_team_other_than_research_never_carries_work_over(tmp_path):
    store = TeamRunStore(tmp_path / "team_runs.db")
    _interrupted_run(store)
    team_dir = tmp_path / "screener"
    (team_dir).mkdir()
    (team_dir / "TEAM.md").write_text("---\nname: screener\nmanager_prompt_file: manager_prompt.md\ntools: []\nskills: []\n---\n", encoding="utf-8")
    (team_dir / "manager_prompt.md").write_text("You screen.", encoding="utf-8")
    seen: list[Any] = []

    class Recording(FakeLLM):
        def chat(self, messages, tools=None):
            seen.append(messages)
            return {"content": "done"}

    TeamManager(team_dir, full_registry=ToolRegistry(), llm=Recording(), run_store=store, triggered_by_session_id=SESSION).run("go")
    assert "RSI dip" not in " ".join(str(m.get("content", "")) for m in seen[0])
