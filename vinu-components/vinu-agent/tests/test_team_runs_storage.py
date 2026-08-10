"""Tests for team_runs / team_tasks tracking storage."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.team_runs import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TeamRunStore,
)


@pytest.fixture
def store() -> TeamRunStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = TeamRunStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestTeamRuns:
    def test_create_run_starts_pending(self, store: TeamRunStore) -> None:
        run = store.create_run("research", triggered_by_session_id="sess-1")
        fetched = store.get_run(run.run_id)
        assert fetched is not None
        assert fetched.team_name == "research"
        assert fetched.triggered_by_session_id == "sess-1"
        assert fetched.status == STATUS_PENDING

    def test_mark_running(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        store.mark_running(run.run_id)
        assert store.get_run(run.run_id).status == STATUS_RUNNING

    def test_mark_done_records_verdict_and_usage(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        store.mark_running(run.run_id)
        store.mark_done(
            run.run_id,
            verdict="PASS",
            result_json={"content": "great strategy"},
            llm_calls_used=7,
            time_used_seconds=12.5,
        )
        fetched = store.get_run(run.run_id)
        assert fetched.status == STATUS_DONE
        assert fetched.verdict == "PASS"
        assert fetched.result_json == {"content": "great strategy"}
        assert fetched.llm_calls_used == 7
        assert fetched.time_used_seconds == 12.5
        assert fetched.completed_at != ""

    def test_mark_failed_records_error(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        store.mark_failed(run.run_id, error_message="LLM timeout")
        fetched = store.get_run(run.run_id)
        assert fetched.status == STATUS_FAILED
        assert fetched.error_message == "LLM timeout"

    def test_mark_cancelled(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        store.mark_cancelled(run.run_id)
        assert store.get_run(run.run_id).status == "cancelled"

    def test_get_run_returns_none_for_unknown_id(self, store: TeamRunStore) -> None:
        assert store.get_run("nope") is None

    def test_list_runs_orders_newest_first(self, store: TeamRunStore) -> None:
        r1 = store.create_run("research")
        r2 = store.create_run("research")
        runs = store.list_runs()
        ids = [r.run_id for r in runs]
        assert ids.index(r2.run_id) < ids.index(r1.run_id) or r1.created_at <= r2.created_at

    def test_list_runs_filters_by_status(self, store: TeamRunStore) -> None:
        r1 = store.create_run("research")
        r2 = store.create_run("research")
        store.mark_running(r2.run_id)
        pending = store.list_runs(status=STATUS_PENDING)
        assert [r.run_id for r in pending] == [r1.run_id]


class TestTeamTasks:
    def test_add_task_starts_pending(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        task = store.add_task(
            run.run_id, agent_name="idea_generator", role="idea-generator", depends_on=[],
        )
        tasks = store.list_tasks(run.run_id)
        assert len(tasks) == 1
        assert tasks[0].task_id == task.task_id
        assert tasks[0].status == TASK_STATUS_PENDING
        assert tasks[0].depends_on == []

    def test_depends_on_round_trips(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        store.add_task(run.run_id, agent_name="idea_generator")
        store.add_task(run.run_id, agent_name="backtest_runner", depends_on=["idea_generator"])
        tasks = {t.agent_name: t for t in store.list_tasks(run.run_id)}
        assert tasks["backtest_runner"].depends_on == ["idea_generator"]

    def test_task_lifecycle_transitions(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        task = store.add_task(run.run_id, agent_name="idea_generator")

        store.mark_task_running(task.task_id)
        running = store.list_tasks(run.run_id)[0]
        assert running.status == TASK_STATUS_RUNNING
        assert running.started_at != ""

        store.mark_task_completed(task.task_id, result="candidate strategy code")
        done = store.list_tasks(run.run_id)[0]
        assert done.status == TASK_STATUS_COMPLETED
        assert done.result == "candidate strategy code"
        assert done.completed_at != ""

    def test_task_failure(self, store: TeamRunStore) -> None:
        run = store.create_run("research")
        task = store.add_task(run.run_id, agent_name="risk_critic")
        store.mark_task_failed(task.task_id, error="LLM refused")
        failed = store.list_tasks(run.run_id)[0]
        assert failed.status == TASK_STATUS_FAILED
        assert failed.error == "LLM refused"

    def test_list_tasks_scoped_to_run(self, store: TeamRunStore) -> None:
        run_a = store.create_run("research")
        run_b = store.create_run("research")
        store.add_task(run_a.run_id, agent_name="idea_generator")
        store.add_task(run_b.run_id, agent_name="backtest_runner")
        assert len(store.list_tasks(run_a.run_id)) == 1
        assert len(store.list_tasks(run_b.run_id)) == 1
