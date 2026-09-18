"""Tests for analysis A (angle trust trajectories)."""

from __future__ import annotations

import pytest

from vinu_research.models import AngleCalibrationEntry, Artifact

from vinu_reflection.reflection import angle_trust


@pytest.fixture
def strategy_store(tmp_path, monkeypatch):
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return angle_trust.get_strategy_store()


def _seed_entry(strategy_store, *, angle_name: str, artifact_id: str, brier: float, correct: bool = True) -> None:
    strategy_store.append_angle_calibration_entry(
        AngleCalibrationEntry(
            angle_name=angle_name,
            artifact_id=artifact_id,
            forecast_direction="up",
            actual_return_pct=1.0,
            brier_score=brier,
            directional_correct=correct,
        )
    )


class TestAngleTrustRun:
    def test_no_data_returns_no_findings(self, strategy_store):
        assert angle_trust.run({}) == []

    def test_below_window_minimum_is_skipped(self, strategy_store):
        strategy_store.upsert_artifact(
            Artifact(artifact_id="a1", type="trade_plan", name="a1", universe=["AAPL"])
        )
        for i in range(40):
            _seed_entry(strategy_store, angle_name="dlinear", artifact_id="a1", brier=0.1)
        assert angle_trust.run({}) == []

    def test_degraded_brier_in_recent_window_is_flagged(self, strategy_store):
        strategy_store.upsert_artifact(
            Artifact(artifact_id="a1", type="trade_plan", name="a1", universe=["AAPL"], regime_tag="trend")
        )
        # 90 reference entries, tightly good (brier=0.1).
        for i in range(90):
            _seed_entry(strategy_store, angle_name="dlinear", artifact_id="a1", brier=0.1)
        # 30 recent entries, much worse (brier=0.6 -- also breaches the
        # domain floor).
        for i in range(30):
            _seed_entry(strategy_store, angle_name="dlinear", artifact_id="a1", brier=0.6, correct=False)

        findings = angle_trust.run({})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "angle"
        assert finding.scope_key == "dlinear"
        assert finding.metric_name == "brier_trend"
        assert finding.primary_metric == pytest.approx(0.5, abs=1e-6)  # 0.6 - 0.1
        assert finding.domain_floor_breached is True
        assert finding.evidence_count == 120
        assert finding.signal_json["directional_accuracy"] == 0.0
        assert finding.signal_json["regime_breakdown"] == {"trend": {"n": 30, "brier": pytest.approx(0.6)}}

    def test_stable_brier_has_low_psi_not_domain_floor(self, strategy_store):
        # run() itself doesn't filter by severity -- that's write_finding's
        # job (vinu-infra/reflection.py) -- so a stable angle still
        # produces a Finding, just one with a low `psi` that write_finding
        # would later classify as `routine` and not write.
        strategy_store.upsert_artifact(
            Artifact(artifact_id="a1", type="trade_plan", name="a1", universe=["AAPL"])
        )
        for i in range(120):
            _seed_entry(strategy_store, angle_name="dlinear", artifact_id="a1", brier=0.2)

        findings = angle_trust.run({})
        assert len(findings) == 1
        assert findings[0].psi < 0.1
        assert findings[0].domain_floor_breached is False

    def test_multiple_angles_evaluated_independently(self, strategy_store):
        strategy_store.upsert_artifact(
            Artifact(artifact_id="a1", type="trade_plan", name="a1", universe=["AAPL"])
        )
        for i in range(90):
            _seed_entry(strategy_store, angle_name="dlinear", artifact_id="a1", brier=0.1)
        for i in range(30):
            _seed_entry(strategy_store, angle_name="dlinear", artifact_id="a1", brier=0.6)
        # tft only has 40 entries total -- below the 120 minimum.
        for i in range(40):
            _seed_entry(strategy_store, angle_name="tft", artifact_id="a1", brier=0.1)

        findings = angle_trust.run({})
        assert {f.scope_key for f in findings} == {"dlinear"}
