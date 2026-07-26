from __future__ import annotations

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.forecast_skill import (
    ForecastSkillConfig,
    compute_brier_score,
    compute_calibration,
    compute_directional_error,
    generate_forecast,
)
from vinu_research.models import CalibrationEntry, Forecast


class TestBrierScore:
    def test_perfect_long_call(self) -> None:
        assert compute_brier_score("long", 1.0, 0.03) == 0.0

    def test_wrong_long_call(self) -> None:
        assert compute_brier_score("long", 1.0, -0.03) == 1.0

    def test_neutral_always_zero(self) -> None:
        # Neutral forecasts always predict class 0.5 with prob 0.5 -> zero squared error,
        # since a "no call" forecast can't be scored against a directional outcome.
        assert compute_brier_score("neutral", 0.9, 0.03) == pytest.approx(0.0)


class TestDirectionalError:
    def test_long_correct(self) -> None:
        assert compute_directional_error("long", 0.02) is True

    def test_long_incorrect(self) -> None:
        assert compute_directional_error("long", -0.02) is False

    def test_short_correct(self) -> None:
        assert compute_directional_error("short", -0.02) is True

    def test_neutral_never_correct(self) -> None:
        assert compute_directional_error("neutral", 0.02) is False


class TestComputeCalibration:
    def test_empty_entries_fails_closed(self) -> None:
        result = compute_calibration([])
        assert result.passed is False
        assert result.n_entries == 0

    def test_below_min_window_fails_closed(self) -> None:
        entries = [
            CalibrationEntry(
                artifact_id="a1", forecast_direction="long",
                actual_return_pct=0.02, directional_correct=True, brier_score=0.0,
            )
            for _ in range(3)
        ]
        result = compute_calibration(entries, ForecastSkillConfig(min_calibration_window=10))
        assert result.passed is False
        assert any("insufficient" in r for r in result.reasons)

    def test_skillful_entries_pass(self) -> None:
        entries = [
            CalibrationEntry(
                artifact_id="a1", forecast_direction="long",
                actual_return_pct=0.02, directional_correct=True, brier_score=0.01,
                forecast_magnitude_pct=0.02, magnitude_error=0.05,
            )
            for _ in range(12)
        ]
        result = compute_calibration(entries, ForecastSkillConfig(min_calibration_window=10))
        assert result.passed is True
        assert result.accuracy == 1.0

    def test_coinflip_entries_fail(self) -> None:
        entries = [
            CalibrationEntry(
                artifact_id="a1", forecast_direction="long",
                actual_return_pct=0.02 if i % 2 == 0 else -0.02,
                directional_correct=(i % 2 == 0), brier_score=0.25,
            )
            for i in range(12)
        ]
        result = compute_calibration(entries, ForecastSkillConfig(min_calibration_window=10))
        assert result.passed is False


class _StubLlmClient:
    def __init__(self, response: dict | None) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    async def chat_json(self, system: str, user: str) -> dict | None:
        self.calls.append((system, user))
        return self._response


class TestGenerateForecast:
    async def test_valid_llm_response(self) -> None:
        stub = _StubLlmClient({
            "direction": "long",
            "confidence": 0.7,
            "magnitude_pct": 0.03,
            "magnitude_std": 0.01,
            "horizon_days": 5,
            "reasoning": "trend continuation",
        })
        forecast = await generate_forecast(
            "AAPL", {"gap_fill_rate": {"mean": 0.5}}, {"status": "ok"},
            ResearchConfig(), llm_client=stub,
        )
        assert isinstance(forecast, Forecast)
        assert forecast.direction == "long"
        assert forecast.confidence == 0.7
        assert forecast.horizon_days == 5
        assert len(stub.calls) == 1

    async def test_llm_failure_falls_back_to_neutral(self) -> None:
        stub = _StubLlmClient(None)
        forecast = await generate_forecast(
            "AAPL", {}, {"status": "insufficient_data"}, ResearchConfig(), llm_client=stub,
        )
        assert forecast.direction == "neutral"
        assert forecast.confidence == 0.0

    async def test_confidence_clamped_to_unit_interval(self) -> None:
        stub = _StubLlmClient({
            "direction": "short",
            "confidence": 1.7,
            "magnitude_pct": 0.02,
            "magnitude_std": 0.01,
            "horizon_days": 1,
        })
        forecast = await generate_forecast(
            "AAPL", {}, {"status": "ok"}, ResearchConfig(), llm_client=stub,
        )
        assert forecast.confidence == 1.0
