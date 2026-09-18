"""Tests for analysis W (threshold calibration drift, bracket_partial +
rebalance_protect checkpoints)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.calibration_log import record

from vinu_reflection.reflection import threshold_calibration


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _log_path(data_root: Path) -> Path:
    return data_root / "calibration_log.jsonl"


def _seed(data_root: Path, checkpoint: str, field: str, values: list[float]) -> None:
    log_path = _log_path(data_root)
    for v in values:
        record(checkpoint, {field: v}, log_path=log_path)


class TestThresholdCalibrationRun:
    def test_no_data_returns_no_findings(self, data_root):
        assert threshold_calibration.run({"vinu_live": data_root}) == []

    def test_below_window_minimum_is_skipped(self, data_root):
        _seed(data_root, "bracket_partial", "r_multiple", [1.0] * 20)
        assert threshold_calibration.run({"vinu_live": data_root}) == []

    def test_drifting_checkpoint_is_flagged(self, data_root):
        _seed(data_root, "bracket_partial", "r_multiple", [1.0] * 45)
        _seed(data_root, "bracket_partial", "r_multiple", [4.0] * 15)

        findings = threshold_calibration.run({"vinu_live": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "system"
        assert finding.scope_key == "bracket_partial"
        assert finding.metric_name == "threshold_behavior_drift"
        assert finding.primary_metric == pytest.approx(3.0, abs=1e-6)
        assert finding.psi > 0.25
        assert finding.evidence_count == 60

    def test_stable_checkpoint_has_low_psi(self, data_root):
        _seed(data_root, "rebalance_protect", "favorable_move_pct", [0.05] * 60)

        findings = threshold_calibration.run({"vinu_live": data_root})
        assert len(findings) == 1
        assert findings[0].psi < 0.1

    def test_checkpoints_evaluated_independently(self, data_root):
        _seed(data_root, "bracket_partial", "r_multiple", [1.0] * 45)
        _seed(data_root, "bracket_partial", "r_multiple", [4.0] * 15)
        _seed(data_root, "rebalance_protect", "favorable_move_pct", [0.05] * 60)

        findings = threshold_calibration.run({"vinu_live": data_root})
        by_checkpoint = {f.scope_key: f for f in findings}
        assert "bracket_partial" in by_checkpoint
        assert "rebalance_protect" in by_checkpoint
        assert by_checkpoint["bracket_partial"].psi > 0.25
        assert by_checkpoint["rebalance_protect"].psi < 0.1

    def test_third_named_checkpoint_has_no_real_writer(self, data_root):
        # thesis-duplicate similarity cutoff -- the design doc's third
        # named checkpoint -- has no real call site anywhere in the
        # codebase (verified while implementing); not evaluated here.
        assert "thesis_duplicate" not in threshold_calibration.CHECKPOINT_FIELDS
