"""Tests for MaturityAssessor (_maturity_assessor.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry

from vinu_reflection.reflection import _maturity_assessor as ma
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
    return ma.get_strategy_store()


def _add_artifact(strategy_store, artifact_id: str, regime_tag: str = "") -> None:
    strategy_store.upsert_artifact(
        Artifact(artifact_id=artifact_id, type="trade_plan", name=artifact_id, universe=["AAPL"], regime_tag=regime_tag)
    )


def _add_entry(
    strategy_store, artifact_id: str, *, correct: bool, brier: float = 0.1, timestamp: str = ""
) -> None:
    strategy_store.append_calibration_entry(
        CalibrationEntry(
            artifact_id=artifact_id,
            forecast_direction="long",
            actual_return_pct=0.02 if correct else -0.02,
            brier_score=brier,
            directional_correct=correct,
            timestamp=timestamp,
        )
    )


class TestAssessTiers:
    def test_no_data_is_cold_start(self, performance_store, strategy_store, data_root):
        result = ma.assess({"vinu_agent": data_root})
        assert result.tier == ma.TIER_COLD_START
        assert result.n_real_trades == 0
        assert result.n_paper_trading_days == 0
        assert result.directional_accuracy == 0.0
        assert result.regime_coverage == []

    def test_paper_only_when_paper_history_exists_but_no_real_trades(
        self, performance_store, strategy_store, data_root
    ):
        performance_store.record_daily_returns("art_1", [0.01] * ma.MIN_PAPER_DAYS)
        _add_artifact(strategy_store, "art_1")

        result = ma.assess({"vinu_agent": data_root})
        assert result.tier == ma.TIER_PAPER_ONLY
        assert result.n_real_trades == 0

    def test_early_live_when_real_trades_below_mature_floor(
        self, performance_store, strategy_store, data_root
    ):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        for _ in range(5):
            _add_entry(strategy_store, "art_1", correct=True)

        result = ma.assess({"vinu_agent": data_root})
        assert result.tier == ma.TIER_EARLY_LIVE
        assert result.n_real_trades == 5

    def test_early_live_when_enough_trades_but_not_enough_regimes(
        self, performance_store, strategy_store, data_root
    ):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        for _ in range(ma.MATURE_MIN_TRADES):
            _add_entry(strategy_store, "art_1", correct=True)

        result = ma.assess({"vinu_agent": data_root})
        assert result.n_real_trades == ma.MATURE_MIN_TRADES
        assert len(result.regime_coverage) == 1
        assert result.tier == ma.TIER_EARLY_LIVE

    def test_mature_when_enough_trades_and_regimes(self, performance_store, strategy_store, data_root):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        _add_artifact(strategy_store, "art_2", regime_tag="range")
        for _ in range(ma.MATURE_MIN_TRADES // 2):
            _add_entry(strategy_store, "art_1", correct=True)
            _add_entry(strategy_store, "art_2", correct=True)

        result = ma.assess({"vinu_agent": data_root})
        assert result.n_real_trades == ma.MATURE_MIN_TRADES
        assert result.regime_coverage == ["range", "trend"]
        assert result.tier == ma.TIER_MATURE


class TestAssessSignals:
    def test_directional_accuracy_and_brier_mean(self, performance_store, strategy_store, data_root):
        _add_artifact(strategy_store, "art_1")
        _add_entry(strategy_store, "art_1", correct=True, brier=0.1)
        _add_entry(strategy_store, "art_1", correct=True, brier=0.3)
        _add_entry(strategy_store, "art_1", correct=False, brier=0.5)

        result = ma.assess({"vinu_agent": data_root})
        assert result.directional_accuracy == pytest.approx(2 / 3)
        assert result.brier_mean == pytest.approx(0.3)

    def test_live_trade_fraction(self, performance_store, strategy_store, data_root):
        # 2 artifacts with real paper history; only 1 of them ever got a
        # real calibration entry (promoted) -- fraction should be 1/2.
        performance_store.record_daily_returns("art_1", [0.01] * ma.MIN_PAPER_DAYS)
        performance_store.record_daily_returns("art_2", [0.01] * ma.MIN_PAPER_DAYS)
        _add_artifact(strategy_store, "art_1")
        _add_artifact(strategy_store, "art_2")
        _add_entry(strategy_store, "art_1", correct=True)

        result = ma.assess({"vinu_agent": data_root})
        assert result.live_trade_fraction == pytest.approx(0.5)

    def test_artifact_without_regime_tag_excluded_from_coverage(
        self, performance_store, strategy_store, data_root
    ):
        _add_artifact(strategy_store, "art_1", regime_tag="")
        _add_entry(strategy_store, "art_1", correct=True)

        result = ma.assess({"vinu_agent": data_root})
        assert result.regime_coverage == []

    def test_tier_ordinal_ordering(self):
        assessment = ma.MaturityAssessment(
            tier=ma.TIER_EARLY_LIVE,
            n_real_trades=1,
            n_paper_trading_days=0,
            directional_accuracy=0.0,
            brier_mean=0.0,
            live_trade_fraction=0.0,
            regime_coverage=[],
        )
        assert assessment.tier_ordinal == 2


class TestRecentFormReading:
    def test_none_below_evidence_floor(self, performance_store, strategy_store, data_root):
        _add_artifact(strategy_store, "art_1")
        for i in range(ma.MIN_RECENT_FORM_ENTRIES - 1):
            _add_entry(strategy_store, "art_1", correct=True, timestamp=f"2026-09-{i + 1:02d}T00:00:00")

        assert ma.recent_form_reading({"vinu_agent": data_root}) is None

    def test_improving_when_majority_of_recent_correct(self, performance_store, strategy_store, data_root):
        _add_artifact(strategy_store, "art_1")
        outcomes = [False, False, True, True, True]  # 3 correct of last 5
        for i, correct in enumerate(outcomes):
            _add_entry(strategy_store, "art_1", correct=correct, timestamp=f"2026-09-{i + 1:02d}T00:00:00")

        assert ma.recent_form_reading({"vinu_agent": data_root}) == "improving"

    def test_degrading_when_majority_of_recent_incorrect(self, performance_store, strategy_store, data_root):
        _add_artifact(strategy_store, "art_1")
        outcomes = [True, True, False, False, False]  # 3 incorrect of last 5
        for i, correct in enumerate(outcomes):
            _add_entry(strategy_store, "art_1", correct=correct, timestamp=f"2026-09-{i + 1:02d}T00:00:00")

        assert ma.recent_form_reading({"vinu_agent": data_root}) == "degrading"

    def test_only_most_recent_n_considered(self, performance_store, strategy_store, data_root):
        _add_artifact(strategy_store, "art_1")
        # 5 old, all wrong -- would read "degrading" if included.
        for i in range(5):
            _add_entry(strategy_store, "art_1", correct=False, timestamp=f"2026-01-{i + 1:02d}T00:00:00")
        # 5 new, all correct -- should be all that matters.
        for i in range(5):
            _add_entry(strategy_store, "art_1", correct=True, timestamp=f"2026-09-{i + 1:02d}T00:00:00")

        assert ma.recent_form_reading({"vinu_agent": data_root}) == "improving"
