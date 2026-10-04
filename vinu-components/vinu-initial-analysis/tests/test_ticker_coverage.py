from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vinu_infra import model_policy as model_policy_module
from vinu_infra import system_manifest as system_manifest_module
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.ticker_coverage import (
    NOT_REQUIRED,
    PENDING,
    _days_stale,
    build_ticker_coverage,
)


def _angle(name: str, category: str) -> dict:
    return {"name": name, "spec": {"category": category}}


_ALL_ANGLES = [
    _angle("shock_personality", "raw_data"),
    _angle("chronos", "model"),
    _angle("moirai", "model"),  # permanently disabled regardless of tag
    _angle("arima", "raw_data"),
]


def _run_log(tmp_path: Path) -> RunLog:
    return RunLog(tmp_path / "runs.db")


@pytest.fixture(autouse=True)
def _reset_policy(monkeypatch):
    monkeypatch.delenv("VINU_MODELS_ENABLED", raising=False)
    importlib.reload(model_policy_module)
    importlib.reload(system_manifest_module)
    # No angle is permanently disabled in the real system any more (moirai was removed); the mechanism is still
    # pinned here with a stand-in set.
    monkeypatch.setattr(system_manifest_module, "PERMANENTLY_DISABLED_ANGLES", frozenset({"moirai"}))
    yield
    importlib.reload(model_policy_module)
    importlib.reload(system_manifest_module)


class TestBuildTickerCoverage:
    def test_new_ticker_all_required_angles_pending(self, tmp_path):
        run_log = _run_log(tmp_path)
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["ticker"] == "AAPL"
        assert coverage["start_date"] is None
        assert coverage["end_date"] is None
        assert coverage["models_enabled"] is None
        assert coverage["angles_with_data"] == 0
        assert coverage["angle_count"] == 4
        # moirai is permanently disabled -- never "pending", even though
        # its own spec.yaml says category: model
        assert coverage["angles"]["moirai"] == NOT_REQUIRED
        # models are on by default -- chronos IS required, and pending
        assert coverage["angles"]["chronos"] == PENDING
        assert coverage["angles"]["shock_personality"] == PENDING
        assert coverage["angles"]["arima"] == PENDING
        assert coverage["overall_status"] == PENDING

    def test_models_off_marks_model_angles_not_required(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
        importlib.reload(model_policy_module)
        importlib.reload(system_manifest_module)
        run_log = _run_log(tmp_path)
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["angles"]["chronos"] == NOT_REQUIRED
        assert coverage["angles"]["moirai"] == NOT_REQUIRED
        # raw_data angles are untouched by the MODELS switch -- still pending
        assert coverage["angles"]["shock_personality"] == PENDING
        assert coverage["required_angle_count"] == 2  # shock_personality + arima only

    def test_reports_real_status_and_date_range_once_run(self, tmp_path):
        run_log = _run_log(tmp_path)
        run_log.record_run(
            "AAPL", "shock_personality", "run-1",
            analysis_from=1700000000, analysis_until=1700100000,
            policy_version="p1", models_enabled=True,
        )
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["angles"]["shock_personality"]["status"] == "completed"
        assert coverage["angles_with_data"] == 1
        assert coverage["start_date"] is not None
        assert coverage["end_date"] is not None

    def test_real_data_wins_over_not_required_label(self, tmp_path, monkeypatch):
        """An angle that genuinely ran before models were later turned off
        must keep showing its real completed status -- not_required only
        explains an ABSENCE, it never overwrites real history."""
        run_log = _run_log(tmp_path)
        run_log.record_run("AAPL", "chronos", "run-1", status="completed", models_enabled=True)

        monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
        importlib.reload(model_policy_module)
        importlib.reload(system_manifest_module)

        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["angles"]["chronos"]["status"] == "completed"

    def test_overall_status_completed_once_every_required_angle_has_run(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
        importlib.reload(model_policy_module)
        importlib.reload(system_manifest_module)
        run_log = _run_log(tmp_path)
        # Only raw_data angles are required with models off -- once both
        # have run, nothing is pending.
        run_log.record_run("AAPL", "shock_personality", "run-1")
        run_log.record_run("AAPL", "arima", "run-2")

        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["overall_status"] == "completed"

    def test_models_enabled_reflects_most_recent_run_not_an_aggregate(self, tmp_path):
        run_log = _run_log(tmp_path)
        run_log.record_run("AAPL", "arima", "run-old", models_enabled=True)
        run_log.record_run("AAPL", "chronos", "run-new", models_enabled=False)
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["models_enabled"] is False

    def test_stale_angle_name_no_longer_on_disk_not_added_as_extra_column(self, tmp_path):
        run_log = _run_log(tmp_path)
        run_log.record_run("AAPL", "some_removed_angle", "run-1")
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert "some_removed_angle" not in coverage["angles"]
        assert coverage["angles_with_data"] == 0

    def test_different_ticker_isolated(self, tmp_path):
        run_log = _run_log(tmp_path)
        run_log.record_run("AAPL", "arima", "run-1")
        coverage = build_ticker_coverage(run_log, "MSFT", _ALL_ANGLES)
        assert coverage["angles_with_data"] == 0
        assert coverage["overall_status"] == PENDING


class TestDaysStale:
    """item #15 option (a): "a deliberately small, low-risk first step"
    -- makes a coverage gap visible without deciding whether/how to
    automate filling it. Computed fresh at read time from each angle's
    own analysis_until, never stored."""

    def test_a_run_from_today_reports_zero_days_stale(self, tmp_path):
        run_log = _run_log(tmp_path)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        run_log.record_run("AAPL", "shock_personality", "run-1", analysis_until=now_ts)
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["angles"]["shock_personality"]["days_stale"] == 0

    def test_a_run_from_60_days_ago_reports_60_days_stale(self, tmp_path):
        run_log = _run_log(tmp_path)
        sixty_days_ago_ts = int((datetime.now(timezone.utc) - timedelta(days=60)).timestamp())
        run_log.record_run("AAPL", "shock_personality", "run-1", analysis_until=sixty_days_ago_ts)
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["angles"]["shock_personality"]["days_stale"] == 60

    def test_never_run_angle_is_a_plain_pending_string_not_a_dict(self, tmp_path):
        """No analysis_until exists at all for an angle that's never run --
        it stays the plain PENDING/NOT_REQUIRED string this module already
        used, not a dict with a meaningless days_stale."""
        run_log = _run_log(tmp_path)
        coverage = build_ticker_coverage(run_log, "AAPL", _ALL_ANGLES)
        assert coverage["angles"]["arima"] == PENDING

    def test_helper_returns_none_for_missing_or_unparseable_input(self) -> None:
        assert _days_stale(None) is None
        assert _days_stale("") is None
        assert _days_stale("not-a-real-date") is None

    def test_helper_treats_a_naive_iso_string_as_utc(self) -> None:
        naive = (datetime.now(timezone.utc) - timedelta(days=10)).replace(tzinfo=None).isoformat()
        assert _days_stale(naive) == 10
