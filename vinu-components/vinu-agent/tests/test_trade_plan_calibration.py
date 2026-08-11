"""Tests for the Calibration Tracker wiring -- Phase 8 (New-talk-agents/
new-thinking/new-restructure/phases/phase-8-summary-agent-polish/). See
agent/trade_plan_calibration.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.trade_plan_calibration import get_trade_plan_calibration
from vinu_research.models import Artifact, CalibrationEntry
from vinu_research.storage.strategy_store import SqliteStrategyStore


def _entry(artifact_id: str, directional_correct: bool, brier: float = 0.1) -> CalibrationEntry:
    return CalibrationEntry(
        artifact_id=artifact_id, forecast_direction="up", actual_return_pct=0.02,
        forecast_magnitude_pct=0.02, brier_score=brier, directional_correct=directional_correct,
        magnitude_error=0.01, timestamp="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def real_strategy_store(monkeypatch):
    data_root = Path(tempfile.mkdtemp())
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(data_root))
    store = SqliteStrategyStore(data_root / "strategy_store.db")
    yield store
    store.close()


@pytest.fixture
def artifact_id(real_strategy_store) -> str:
    artifact = Artifact.create("trade_plan", "test-plan", universe=["AAPL"])
    real_strategy_store.upsert_artifact(artifact)
    return artifact.artifact_id


class TestGetTradePlanCalibrationInProcess:
    def test_reads_real_entries_in_process(self, real_strategy_store, artifact_id) -> None:
        for _ in range(12):
            real_strategy_store.append_calibration_entry(_entry(artifact_id, True))

        result = get_trade_plan_calibration(artifact_id)

        assert result["source"] == "in_process"
        assert result["n_entries"] == 12
        assert result["passed"] is True

    def test_below_min_window_reports_insufficient_and_fails(self, real_strategy_store, artifact_id) -> None:
        for _ in range(3):
            real_strategy_store.append_calibration_entry(_entry(artifact_id, True))

        result = get_trade_plan_calibration(artifact_id, min_window=10)

        assert result["n_entries"] == 3
        assert result["passed"] is False
        assert any("too small" in r for r in result["reasons"])

    def test_unknown_artifact_id_has_zero_entries_not_an_error(self, real_strategy_store) -> None:
        result = get_trade_plan_calibration("art_never_recorded")
        assert result["source"] == "in_process"
        assert result["n_entries"] == 0
        assert result["passed"] is False


class TestGetTradePlanCalibrationHttpFallback:
    def test_falls_back_to_http_when_in_process_unavailable(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"n_entries": 12, "passed": True, "reasons": []}

        with patch(
            "vinu_agent.broker.research_link.get_strategy_store", side_effect=RuntimeError("not available"),
        ):
            with patch("httpx.get", return_value=mock_resp) as mock_get:
                result = get_trade_plan_calibration("art_1", research_api_url="http://research-api:8087")

        assert result["source"] == "http"
        assert result["n_entries"] == 12
        assert result["passed"] is True
        assert "art_1" in mock_get.call_args[0][0]

    def test_both_transports_unavailable_reports_distinct_error(self) -> None:
        with patch(
            "vinu_agent.broker.research_link.get_strategy_store", side_effect=RuntimeError("not available"),
        ):
            with patch("httpx.get", side_effect=ConnectionError("research-api down")):
                result = get_trade_plan_calibration("art_1")

        assert result["source"] == "error"
        assert result["passed"] is False


class TestCalibrationTransportAgnostic:
    def test_in_process_and_http_produce_the_same_result_for_identical_input(
        self, real_strategy_store, artifact_id,
    ) -> None:
        """03-test.md: proves the Summary Agent's calibration wiring
        doesn't hardcode an assumption about which transport is active."""
        for _ in range(12):
            real_strategy_store.append_calibration_entry(_entry(artifact_id, True))

        in_process_result = get_trade_plan_calibration(artifact_id)

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "n_entries": in_process_result["n_entries"], "passed": in_process_result["passed"],
            "reasons": in_process_result["reasons"],
        }
        with patch(
            "vinu_agent.broker.research_link.get_strategy_store", side_effect=RuntimeError("simulate not migrated"),
        ):
            with patch("httpx.get", return_value=mock_resp):
                http_result = get_trade_plan_calibration(artifact_id)

        assert in_process_result["n_entries"] == http_result["n_entries"]
        assert in_process_result["passed"] == http_result["passed"]
