from __future__ import annotations

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.forecast_skill import (
    ForecastSkillConfig,
    _build_forecast_prompt,
    compute_angle_calibration,
    compute_brier_score,
    compute_calibration,
    compute_directional_error,
    generate_forecast,
)
from vinu_research.models import AngleCalibrationEntry, CalibrationEntry, Forecast


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


class TestComputeAngleCalibration:
    def test_empty_entries(self) -> None:
        result = compute_angle_calibration("patchtst", [])
        assert result.angle_name == "patchtst"
        assert result.n_entries == 0

    def test_aggregates_across_entries(self) -> None:
        entries = [
            AngleCalibrationEntry(
                angle_name="patchtst", artifact_id=f"a{i}", forecast_direction="long",
                actual_return_pct=0.02, directional_correct=True, brier_score=0.01,
                forecast_magnitude_pct=0.02, magnitude_error=0.05,
            )
            for i in range(5)
        ]
        result = compute_angle_calibration("patchtst", entries)
        assert result.angle_name == "patchtst"
        assert result.n_entries == 5
        assert result.accuracy == 1.0
        assert result.brier_mean == pytest.approx(0.01)

    def test_no_pass_fail_gate_unlike_trade_plan_calibration(self) -> None:
        """AngleCalibrationResult deliberately has no `passed`/`reasons`
        fields at all -- there's no established null-threshold for
        per-angle scoring, see the module docstring."""
        result = compute_angle_calibration("patchtst", [])
        assert not hasattr(result, "passed")
        assert not hasattr(result, "reasons")


class _StubLlmClient:
    def __init__(self, response: dict | None) -> None:
        self._response = response
        self.calls: list[tuple[str, str]] = []

    async def chat_json(self, system: str, user: str, *, raise_on_failure: bool = False) -> dict | None:
        self.calls.append((system, user))
        if self._response is None and raise_on_failure:
            from vinu_infra.llm.retry import LlmCallFailed
            raise LlmCallFailed("stub: no response configured")
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

    async def test_llm_failure_raises_instead_of_faking_a_neutral_forecast(self) -> None:
        """A real LLM failure used to be silently substituted with a fake
        neutral forecast (direction="neutral", confidence=0.0) that was
        numerically indistinguishable from a genuine low-signal read --
        a real trade-plan decision could be shaped by a forecast that
        never actually happened. See
        missing-pieces-of-system/llm-configuration-settings-system/."""
        from vinu_infra.llm.retry import LlmCallFailed

        stub = _StubLlmClient(None)
        with pytest.raises(LlmCallFailed):
            await generate_forecast(
                "AAPL", {}, {"status": "insufficient_data"}, ResearchConfig(), llm_client=stub,
            )

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

    async def test_angle_digest_reaches_the_prompt(self) -> None:
        """Regression for the '2 of 28 angles' gate-conflict: forecast_skill
        used to only ever see shock_personality/shock_clustering as
        structured input, with every other angle collapsed into free-text
        prose -- see high-expectations gate-conflict audit."""
        stub = _StubLlmClient({
            "direction": "long", "confidence": 0.6, "magnitude_pct": 0.01,
            "magnitude_std": 0.01, "horizon_days": 1,
        })
        summary_context = {
            "summary": "AAPL looks constructive.",
            "angles_with_data": 2, "angle_count": 2, "source_run_id": "run-1",
            "angle_digest": {"trend_lifecycle": {"stage": "mature"}, "regime_analysis": {"regime": "bull"}},
        }
        await generate_forecast(
            "AAPL", {}, {"status": "ok"}, ResearchConfig(), llm_client=stub,
            summary_context=summary_context,
        )
        prompt = stub.calls[0][1]
        assert "=== Angle Digest ===" in prompt
        assert "trend_lifecycle.stage: mature" in prompt
        assert "regime_analysis.regime: bull" in prompt


class TestBuildForecastPromptAngleDigest:
    def test_no_digest_omits_the_section(self) -> None:
        prompt = _build_forecast_prompt("AAPL", {}, {}, summary_context=None)
        assert "=== Angle Digest ===" not in prompt

    def test_empty_digest_omits_the_section(self) -> None:
        prompt = _build_forecast_prompt(
            "AAPL", {}, {}, summary_context={"summary": "x", "angle_digest": {}},
        )
        assert "=== Angle Digest ===" not in prompt

    def test_non_dict_angle_entries_are_skipped_not_raised(self) -> None:
        prompt = _build_forecast_prompt(
            "AAPL", {}, {},
            summary_context={"summary": "x", "angle_digest": {"broken": "not-a-dict", "ok": {"a": 1}}},
        )
        assert "ok.a: 1" in prompt
        assert "broken" not in prompt
