from vinu_agent.storage.team_runs import STATUS_DONE, STATUS_FAILED, STATUS_RUNNING, TeamRunStore


def test_runs_left_running_by_a_dead_container_are_failed_and_finished_ones_untouched(tmp_path):
    store = TeamRunStore(tmp_path / "team_runs.db")
    stuck = store.create_run("research")
    store.mark_running(stuck.run_id)
    waiting = store.create_run("screener")                          # still pending
    finished = store.create_run("screener")
    store.mark_done(finished.run_id, verdict="PASS", result_json={}, llm_calls_used=1, time_used_seconds=1.0)

    ids = store.fail_interrupted("interrupted: restart")

    assert set(ids) == {stuck.run_id, waiting.run_id}
    for rid in ids:
        run = store.get_run(rid)
        assert run.status == STATUS_FAILED and "restart" in run.error_message
    assert store.get_run(finished.run_id).status == STATUS_DONE
    assert store.list_runs(status=STATUS_RUNNING) == []
    assert store.fail_interrupted("again") == []                    # nothing left to fail


def test_the_entrypoint_reconciles_before_starting_any_worker():
    from pathlib import Path

    script = (Path(__file__).resolve().parents[1] / "entrypoint.sh").read_text(encoding="utf-8")
    reconcile = script.index("vinu-agent reconcile-runs")
    assert reconcile < script.index("vinu-agent skill-audit-worker &")
    assert reconcile < script.index("vinu-agent planner-worker &")
