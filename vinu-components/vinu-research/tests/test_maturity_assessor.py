"""Tests for vinu-research's own MaturityAssessor copy (maturity_assessor.py),
wired into trade-plan authoring's prompt."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from vinu_research.models import Artifact, CalibrationEntry
from vinu_research.storage.strategy_store import SqliteStrategyStore

from vinu_research import maturity_assessor as ma


@pytest.fixture
def strategy_store(tmp_path) -> SqliteStrategyStore:
    return SqliteStrategyStore(tmp_path / "strategy_store.db")


def _add_artifact(strategy_store, artifact_id: str, regime_tag: str = "") -> None:
    strategy_store.upsert_artifact(
        Artifact(artifact_id=artifact_id, type="trade_plan", name=artifact_id, universe=["AAPL"], regime_tag=regime_tag)
    )


def _add_entry(strategy_store, artifact_id: str, *, correct: bool) -> None:
    strategy_store.append_calibration_entry(
        CalibrationEntry(
            artifact_id=artifact_id,
            forecast_direction="long",
            actual_return_pct=0.02 if correct else -0.02,
            directional_correct=correct,
        )
    )


def _write_paper_performance_db(path: Path, rows: dict[str, list[float]]) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE paper_performance (artifact_id TEXT PRIMARY KEY, returns_json TEXT NOT NULL, "
        "updated_at REAL NOT NULL, meta_json TEXT NOT NULL DEFAULT '{}')"
    )
    for artifact_id, returns in rows.items():
        conn.execute(
            "INSERT INTO paper_performance (artifact_id, returns_json, updated_at) VALUES (?, ?, 0)",
            (artifact_id, json.dumps(returns)),
        )
    conn.commit()
    conn.close()


class TestAssessTiers:
    def test_no_data_is_cold_start(self, strategy_store, tmp_path):
        result = ma.assess(strategy_store, None)
        assert result.tier == ma.TIER_COLD_START
        assert result.n_real_trades == 0
        assert result.n_paper_trading_days == 0

    def test_agent_data_root_none_means_no_paper_visibility(self, strategy_store, tmp_path):
        # agent_data_root=None is the real research-api (HTTP-fallback)
        # posture -- paper history is invisible there by design.
        _add_artifact(strategy_store, "art_1")
        _add_entry(strategy_store, "art_1", correct=True)
        result = ma.assess(strategy_store, None)
        assert result.n_paper_trading_days == 0

    def test_paper_only_when_paper_history_reachable(self, strategy_store, tmp_path):
        agent_root = tmp_path / "agent"
        agent_root.mkdir()
        _write_paper_performance_db(agent_root / "paper_performance.db", {"art_1": [0.01] * ma.MIN_PAPER_DAYS})
        _add_artifact(strategy_store, "art_1")

        result = ma.assess(strategy_store, agent_root)
        assert result.tier == ma.TIER_PAPER_ONLY
        assert result.n_paper_trading_days == ma.MIN_PAPER_DAYS

    def test_missing_paper_performance_db_fails_open(self, strategy_store, tmp_path):
        agent_root = tmp_path / "agent"
        agent_root.mkdir()  # no paper_performance.db written
        result = ma.assess(strategy_store, agent_root)
        assert result.tier == ma.TIER_COLD_START
        assert result.n_paper_trading_days == 0

    def test_early_live_below_mature_floor(self, strategy_store, tmp_path):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        for _ in range(5):
            _add_entry(strategy_store, "art_1", correct=True)

        result = ma.assess(strategy_store, None, mature_min_trades=30)
        assert result.tier == ma.TIER_EARLY_LIVE
        assert result.n_real_trades == 5

    def test_mature_when_enough_trades_and_regimes(self, strategy_store, tmp_path):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        _add_artifact(strategy_store, "art_2", regime_tag="range")
        for _ in range(3):
            _add_entry(strategy_store, "art_1", correct=True)
            _add_entry(strategy_store, "art_2", correct=True)

        result = ma.assess(strategy_store, None, mature_min_trades=6)
        assert result.tier == ma.TIER_MATURE
        assert result.regime_coverage == ["range", "trend"]

    def test_respects_custom_mature_min_trades(self, strategy_store, tmp_path):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        _add_artifact(strategy_store, "art_2", regime_tag="range")
        for _ in range(2):
            _add_entry(strategy_store, "art_1", correct=True)
            _add_entry(strategy_store, "art_2", correct=True)

        assert ma.assess(strategy_store, None, mature_min_trades=10).tier == ma.TIER_EARLY_LIVE
        assert ma.assess(strategy_store, None, mature_min_trades=4).tier == ma.TIER_MATURE


class TestAssessPromptDict:
    def test_as_prompt_dict_shape(self, strategy_store, tmp_path):
        _add_artifact(strategy_store, "art_1", regime_tag="trend")
        _add_entry(strategy_store, "art_1", correct=True)
        _add_entry(strategy_store, "art_1", correct=False)

        result = ma.assess(strategy_store, None)
        d = result.as_prompt_dict()
        assert d["tier"] == ma.TIER_EARLY_LIVE
        assert d["n_real_trades"] == 2
        assert d["directional_accuracy"] == pytest.approx(0.5)
        assert d["regime_coverage"] == ["trend"]
