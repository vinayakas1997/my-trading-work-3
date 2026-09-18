"""Tests for analysis V (paper-vs-live performance predictor)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry

from vinu_reflection.reflection import paper_live_correlation
from vinu_agent.broker.performance_store import PaperPerformanceStore


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


@pytest.fixture
def performance_store(data_root) -> PaperPerformanceStore:
    return PaperPerformanceStore(data_root / "paper_performance.db")


@pytest.fixture
def strategy_store(tmp_path, monkeypatch):
    research_root = tmp_path / "research"
    research_root.mkdir()
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(research_root))
    return paper_live_correlation.get_strategy_store()


def _seed_live_returns(strategy_store, *, artifact_id: str, live_returns: list[float]) -> None:
    strategy_store.upsert_artifact(
        Artifact(artifact_id=artifact_id, type="trade_plan", name=artifact_id, universe=["AAPL"])
    )
    for r in live_returns:
        strategy_store.append_calibration_entry(
            CalibrationEntry(artifact_id=artifact_id, forecast_direction="long", actual_return_pct=r)
        )


class TestPaperLiveCorrelationRun:
    def test_no_data_returns_no_findings(self, performance_store, strategy_store, data_root):
        assert paper_live_correlation.run({"vinu_agent": data_root}) == []

    def test_below_min_sample_artifacts_is_skipped(self, performance_store, strategy_store, data_root):
        # Only 3 artifacts with both paper and live history -- below the
        # design doc's own ">=5 promoted artifacts" floor.
        for i in range(3):
            aid = f"art_{i}"
            performance_store.record_daily_returns(aid, [0.01] * 5)
            _seed_live_returns(strategy_store, artifact_id=aid, live_returns=[0.02])
        assert paper_live_correlation.run({"vinu_agent": data_root}) == []

    def test_artifact_with_too_few_paper_days_excluded(self, performance_store, strategy_store, data_root):
        # 5 well-formed artifacts, plus one with only 2 paper days (below
        # MIN_PAPER_DAYS) that should be excluded, not just under-counted.
        for i in range(5):
            aid = f"good_{i}"
            performance_store.record_daily_returns(aid, [0.01 * (i + 1)] * 5)
            _seed_live_returns(strategy_store, artifact_id=aid, live_returns=[0.02 * (i + 1)])
        performance_store.record_daily_returns("thin", [0.01, 0.02])
        _seed_live_returns(strategy_store, artifact_id="thin", live_returns=[0.05])

        findings = paper_live_correlation.run({"vinu_agent": data_root})
        assert len(findings) == 1
        assert findings[0].evidence_count == 5
        assert findings[0].signal_json["n_promoted_artifacts"] == 5

    def test_artifact_never_promoted_excluded(self, performance_store, strategy_store, data_root):
        # A BENCHING-only artifact (paper returns recorded, never any
        # calibration entry) must not count as promoted.
        for i in range(5):
            aid = f"art_{i}"
            performance_store.record_daily_returns(aid, [0.01 * (i + 1)] * 5)
            _seed_live_returns(strategy_store, artifact_id=aid, live_returns=[0.02 * (i + 1)])
        performance_store.record_daily_returns("never_promoted", [0.05] * 10)
        strategy_store.upsert_artifact(
            Artifact(artifact_id="never_promoted", type="trade_plan", name="never_promoted", universe=["MSFT"])
        )

        findings = paper_live_correlation.run({"vinu_agent": data_root})
        assert len(findings) == 1
        assert findings[0].signal_json["n_promoted_artifacts"] == 5

    def test_strong_positive_correlation(self, performance_store, strategy_store, data_root):
        for i in range(6):
            aid = f"art_{i}"
            paper = 0.01 * (i + 1)
            live = 0.01 * (i + 1)
            performance_store.record_daily_returns(aid, [paper] * 5)
            _seed_live_returns(strategy_store, artifact_id=aid, live_returns=[live])

        findings = paper_live_correlation.run({"vinu_agent": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "system"
        assert finding.scope_key == "paper_vs_live_performance"
        assert finding.metric_name == "paper_live_correlation"
        assert finding.primary_metric == pytest.approx(1.0, abs=1e-6)
        assert finding.signal_json["paper_live_correlation"] == pytest.approx(1.0, abs=1e-6)
        assert finding.domain_floor_breached is False

    def test_negative_correlation_breaches_domain_floor(self, performance_store, strategy_store, data_root):
        for i in range(6):
            aid = f"art_{i}"
            paper = 0.01 * (i + 1)
            live = -0.01 * (i + 1)
            performance_store.record_daily_returns(aid, [paper] * 5)
            _seed_live_returns(strategy_store, artifact_id=aid, live_returns=[live])

        findings = paper_live_correlation.run({"vinu_agent": data_root})
        assert len(findings) == 1
        assert findings[0].primary_metric < 0
        assert findings[0].domain_floor_breached is True
