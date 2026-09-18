"""Tests for analysis H, consistency piece (freeze-manifest drift
detection, cycle-to-cycle)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_reflection.reflection import consistency_freeze


@pytest.fixture
def reflection_data_root(tmp_path) -> Path:
    root = tmp_path / "reflection-data"
    root.mkdir()
    return root


@pytest.fixture
def watched_root(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "watched"
    root.mkdir()
    monkeypatch.setenv("VINU_TEST_CONSISTENCY_DATA_ROOT", str(root))
    (root / "a.txt").write_text("hello", encoding="utf-8")
    return root


class TestConsistencyFreezeRun:
    def test_first_cycle_establishes_baseline_and_writes_nothing(
        self, reflection_data_root, watched_root
    ):
        findings = consistency_freeze.run({"vinu_reflection": reflection_data_root})
        assert findings == []
        state_path = reflection_data_root / consistency_freeze.STATE_FILENAME
        assert state_path.exists()

    def test_no_change_between_cycles_writes_nothing(self, reflection_data_root, watched_root):
        consistency_freeze.run({"vinu_reflection": reflection_data_root})
        findings = consistency_freeze.run({"vinu_reflection": reflection_data_root})
        assert findings == []

    def test_changed_file_is_flagged(self, reflection_data_root, watched_root):
        consistency_freeze.run({"vinu_reflection": reflection_data_root})
        (watched_root / "a.txt").write_text("goodbye", encoding="utf-8")

        findings = consistency_freeze.run({"vinu_reflection": reflection_data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "system"
        assert finding.scope_key == "freeze_manifest"
        assert finding.domain_floor_breached is True
        assert "a.txt" in finding.signal_json["changed"]

    def test_added_file_is_flagged(self, reflection_data_root, watched_root):
        consistency_freeze.run({"vinu_reflection": reflection_data_root})
        (watched_root / "b.txt").write_text("new", encoding="utf-8")

        findings = consistency_freeze.run({"vinu_reflection": reflection_data_root})
        assert len(findings) == 1
        assert "b.txt" in findings[0].signal_json["added"]

    def test_env_var_change_is_flagged(self, reflection_data_root, watched_root, monkeypatch):
        consistency_freeze.run({"vinu_reflection": reflection_data_root})
        monkeypatch.setenv("VINU_SOME_OTHER_FLAG", "changed")

        findings = consistency_freeze.run({"vinu_reflection": reflection_data_root})
        assert len(findings) == 1
        assert "VINU_SOME_OTHER_FLAG" in findings[0].signal_json["env_changed"]

    def test_state_persists_across_separate_run_calls(self, reflection_data_root, watched_root):
        consistency_freeze.run({"vinu_reflection": reflection_data_root})
        # A brand-new call with no in-memory state carried over must still
        # read the persisted prior manifest from disk correctly.
        findings = consistency_freeze.run({"vinu_reflection": reflection_data_root})
        assert findings == []
