"""Tests for analysis M (does the investment-committee debate earn its cost)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry

from vinu_reflection.reflection import debate_value


@pytest.fixture
def strategy_store(tmp_path, monkeypatch):
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return debate_value.get_strategy_store()


def _trade_plan_data(*, with_debate: bool) -> str:
    signals = [{"source": "investment_committee", "direction": "bullish"}] if with_debate else []
    return json.dumps({"forecast": {"signals": signals}})


def _seed_artifact(strategy_store, *, artifact_id: str, with_debate: bool, quality: float, n: int = 10) -> None:
    strategy_store.upsert_artifact(
        Artifact(
            artifact_id=artifact_id,
            type="trade_plan",
            name=artifact_id,
            universe=["AAPL"],
            trade_plan_data=_trade_plan_data(with_debate=with_debate),
        )
    )
    n_correct = round(quality * n)
    for i in range(n):
        strategy_store.append_calibration_entry(
            CalibrationEntry(
                artifact_id=artifact_id,
                forecast_direction="up",
                actual_return_pct=1.0,
                directional_correct=(i < n_correct),
            )
        )


class TestDebateValueRun:
    def test_no_data_returns_no_findings(self, strategy_store):
        assert debate_value.run({}) == []

    def test_below_group_minimum_is_skipped(self, strategy_store):
        for i in range(5):
            _seed_artifact(strategy_store, artifact_id=f"a-{i}", with_debate=True, quality=1.0)
            _seed_artifact(strategy_store, artifact_id=f"b-{i}", with_debate=False, quality=1.0)
        assert debate_value.run({}) == []

    def test_debated_artifacts_underperform_is_flagged(self, strategy_store):
        for i in range(10):
            _seed_artifact(strategy_store, artifact_id=f"debated-{i}", with_debate=True, quality=0.2)
        for i in range(10):
            _seed_artifact(strategy_store, artifact_id=f"plain-{i}", with_debate=False, quality=0.9)

        findings = debate_value.run({})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_key == "investment_committee"
        assert finding.primary_metric < 0  # debate underperformed
        assert finding.metric_name == "with_debate_outcome_delta"
        assert finding.evidence_count == 20
        assert finding.psi > 0.25

    def test_artifacts_without_calibration_entries_are_excluded(self, strategy_store):
        for i in range(10):
            strategy_store.upsert_artifact(
                Artifact(
                    artifact_id=f"nocal-{i}",
                    type="trade_plan",
                    name=f"nocal-{i}",
                    universe=["AAPL"],
                    trade_plan_data=_trade_plan_data(with_debate=True),
                )
            )
        assert debate_value.run({}) == []

    def test_malformed_trade_plan_data_treated_as_no_debate(self, strategy_store):
        strategy_store.upsert_artifact(
            Artifact(
                artifact_id="broken",
                type="trade_plan",
                name="broken",
                universe=["AAPL"],
                trade_plan_data="not json",
            )
        )
        for i in range(10):
            strategy_store.append_calibration_entry(
                CalibrationEntry(
                    artifact_id="broken", forecast_direction="up",
                    actual_return_pct=1.0, directional_correct=True,
                )
            )
        # Not enough evidence to write a finding, but must not raise.
        assert debate_value.run({}) == []
