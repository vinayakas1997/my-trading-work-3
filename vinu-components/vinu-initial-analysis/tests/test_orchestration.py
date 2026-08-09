from __future__ import annotations

from pathlib import Path

import pytest

from vinu_initial_analysis.storage.orchestration import AngleRunStatus, run_batch


def _tracker(tmp_path: Path) -> AngleRunStatus:
    return AngleRunStatus(tmp_path / "test_orchestration.db")


def test_register_batch_creates_one_pending_row_per_job(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.register_batch("b1", [("AAPL", "garch"), ("AAPL", "lstm"), ("TSLA", "garch")])
    rows = tracker.get_batch_status("b1")
    assert len(rows) == 3
    assert all(r["status"] == "pending" for r in rows)


def test_full_lifecycle_running_to_ok(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.register_batch("b1", [("AAPL", "garch")])
    tracker.mark_running("b1", "AAPL", "garch")
    row = tracker.get_batch_status("b1")[0]
    assert row["status"] == "running"
    assert row["attempts"] == 1
    assert row["started_at"] is not None

    tracker.mark_ok("b1", "AAPL", "garch")
    row = tracker.get_batch_status("b1")[0]
    assert row["status"] == "ok"


def test_mark_failed_records_the_error(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.register_batch("b1", [("AAPL", "garch")])
    tracker.mark_running("b1", "AAPL", "garch")
    tracker.mark_failed("b1", "AAPL", "garch", "ValueError: boom")
    row = tracker.get_batch_status("b1")[0]
    assert row["status"] == "failed"
    assert row["last_error"] == "ValueError: boom"


def test_is_batch_complete_requires_every_row_ok(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.register_batch("b1", [("AAPL", "garch"), ("AAPL", "lstm")])
    assert tracker.is_batch_complete("b1") is False

    tracker.mark_running("b1", "AAPL", "garch")
    tracker.mark_ok("b1", "AAPL", "garch")
    assert tracker.is_batch_complete("b1") is False  # lstm still pending

    tracker.mark_running("b1", "AAPL", "lstm")
    tracker.mark_ok("b1", "AAPL", "lstm")
    assert tracker.is_batch_complete("b1") is True


def test_is_batch_complete_false_for_unknown_batch(tmp_path):
    tracker = _tracker(tmp_path)
    assert tracker.is_batch_complete("does-not-exist") is False


def test_delete_batch_removes_all_its_rows_and_leaves_others(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.register_batch("b1", [("AAPL", "garch")])
    tracker.register_batch("b2", [("TSLA", "garch")])
    deleted = tracker.delete_batch("b1")
    assert deleted == 1
    assert tracker.get_batch_status("b1") == []
    assert len(tracker.get_batch_status("b2")) == 1


def test_stale_running_rows_flags_old_heartbeats_not_fresh_ones(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.register_batch("b1", [("AAPL", "garch"), ("AAPL", "lstm")])
    tracker.mark_running("b1", "AAPL", "garch")
    tracker.mark_running("b1", "AAPL", "lstm")

    # both just started -- neither is stale yet even with a 0-second window
    # in the exact same instant; use a negative window to force "everything
    # counts as stale" and a huge one to force "nothing is stale" instead
    # of racing real wall-clock time in the test.
    assert tracker.stale_running_rows(older_than_seconds=999999) == []
    stale = tracker.stale_running_rows(older_than_seconds=-1)
    assert {r["angle_name"] for r in stale} == {"garch", "lstm"}


def test_run_batch_registers_runs_and_deletes_on_full_success(tmp_path):
    tracker = _tracker(tmp_path)
    calls = []

    def _work(name):
        calls.append(name)
        return f"{name}-result"

    jobs = [
        ("AAPL", "garch", lambda: _work("garch")),
        ("AAPL", "lstm", lambda: _work("lstm")),
    ]
    summary = run_batch(tracker, "b1", jobs)

    assert summary["ok"] is True
    assert summary["results"] == {"AAPL:garch": "garch-result", "AAPL:lstm": "lstm-result"}
    assert summary["errors"] == {}
    assert calls == ["garch", "lstm"]
    # batch fully succeeded -- rows are gone, not kept around
    assert tracker.get_batch_status("b1") == []


def test_run_batch_retries_a_transient_failure_and_recovers(tmp_path):
    tracker = _tracker(tmp_path)
    attempts = {"n": 0}

    def _flaky():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient failure")
        return "recovered"

    summary = run_batch(tracker, "b1", [("AAPL", "flaky_angle", _flaky)], max_attempts=3)
    assert summary["ok"] is True
    assert summary["results"] == {"AAPL:flaky_angle": "recovered"}
    assert attempts["n"] == 2
    assert tracker.get_batch_status("b1") == []  # succeeded -- cleaned up


def test_run_batch_permanent_failure_is_recorded_and_row_survives(tmp_path):
    tracker = _tracker(tmp_path)

    def _always_fails():
        raise ValueError("permanently broken")

    def _succeeds():
        return "fine"

    jobs = [
        ("AAPL", "broken_angle", _always_fails),
        ("AAPL", "good_angle", _succeeds),
    ]
    summary = run_batch(tracker, "b1", jobs, max_attempts=2)

    assert summary["ok"] is False
    assert "AAPL:broken_angle" in summary["errors"]
    assert "ValueError: permanently broken" in summary["errors"]["AAPL:broken_angle"]
    assert summary["results"]["AAPL:good_angle"] == "fine"

    # batch did NOT fully succeed -- rows are NOT deleted, full visibility
    # into what's stuck remains
    rows = {r["angle_name"]: r for r in tracker.get_batch_status("b1")}
    assert rows["broken_angle"]["status"] == "failed"
    assert rows["broken_angle"]["attempts"] == 2  # both attempts counted
    assert rows["good_angle"]["status"] == "ok"


def test_run_batch_max_attempts_is_registered_per_job(tmp_path):
    tracker = _tracker(tmp_path)

    def _always_fails():
        raise RuntimeError("nope")

    run_batch(tracker, "b1", [("AAPL", "x", _always_fails)], max_attempts=5)
    row = tracker.get_batch_status("b1")[0]
    assert row["attempts"] == 5
    assert row["max_attempts"] == 5
