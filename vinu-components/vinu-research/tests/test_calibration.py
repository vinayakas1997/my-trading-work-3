from __future__ import annotations

from vinu_research.calibration import CalibrationGate, CalibrationTracker, get_angle_calibration
from vinu_research.forecast_skill import ForecastSkillConfig
from vinu_research.models import AngleCalibrationEntry, Forecast, TradePlan
from vinu_research.trade_plan_authoring import freeze_trade_plan


class TestCalibrationTracker:
    def test_add_entry_records_correctness(self) -> None:
        tracker = CalibrationTracker("art_1")
        forecast = Forecast(direction="long", confidence=0.8, magnitude_pct=0.02)
        entry = tracker.add_entry(forecast, actual_return_pct=0.03)
        assert entry.directional_correct is True
        assert entry.artifact_id == "art_1"
        assert len(tracker.entries) == 1

    def test_add_entry_wrong_direction(self) -> None:
        tracker = CalibrationTracker("art_1")
        forecast = Forecast(direction="long", confidence=0.8, magnitude_pct=0.02)
        entry = tracker.add_entry(forecast, actual_return_pct=-0.03)
        assert entry.directional_correct is False

    def test_evaluate_delegates_to_compute_calibration(self) -> None:
        tracker = CalibrationTracker("art_1", ForecastSkillConfig(min_calibration_window=2))
        forecast = Forecast(direction="long", confidence=0.9, magnitude_pct=0.02)
        tracker.add_entry(forecast, actual_return_pct=0.03)
        tracker.add_entry(forecast, actual_return_pct=0.03)
        result = tracker.evaluate()
        assert result.n_entries == 2
        assert result.accuracy == 1.0

    def test_clear_resets_entries(self) -> None:
        tracker = CalibrationTracker("art_1")
        forecast = Forecast(direction="long", confidence=0.8, magnitude_pct=0.02)
        tracker.add_entry(forecast, actual_return_pct=0.03)
        tracker.clear()
        assert tracker.entries == []


class TestCalibrationGate:
    def test_closed_with_no_entries(self) -> None:
        tracker = CalibrationTracker("art_1")
        gate = CalibrationGate(tracker, min_window=10)
        assert gate.is_open() is False
        result = gate.check()
        assert result.passed is False
        assert any("window too small" in r for r in result.reasons)

    def test_closed_below_min_window_even_if_skillful(self) -> None:
        tracker = CalibrationTracker("art_1", ForecastSkillConfig(min_calibration_window=2))
        forecast = Forecast(direction="long", confidence=0.9, magnitude_pct=0.02)
        tracker.add_entry(forecast, actual_return_pct=0.03)
        tracker.add_entry(forecast, actual_return_pct=0.03)
        gate = CalibrationGate(tracker, min_window=10)
        assert gate.is_open() is False

    def test_open_when_skillful_and_window_met(self) -> None:
        cfg = ForecastSkillConfig(min_calibration_window=5)
        tracker = CalibrationTracker("art_1", cfg)
        forecast = Forecast(direction="long", confidence=0.9, magnitude_pct=0.02)
        for _ in range(5):
            tracker.add_entry(forecast, actual_return_pct=0.03)
        gate = CalibrationGate(tracker, min_window=5)
        assert gate.is_open() is True
        result = gate.check()
        assert result.passed is True


def _frozen_artifact_id(strategy_store) -> str:
    plan = TradePlan(symbol="AAPL", timeframe="daily", direction="long")
    return freeze_trade_plan(strategy_store, plan).artifact_id


class TestGetAngleCalibration:
    def test_no_entries_returns_zero_not_an_error(self, strategy_store) -> None:
        result = get_angle_calibration(strategy_store, "patchtst")
        assert result.angle_name == "patchtst"
        assert result.n_entries == 0

    def test_reads_back_persisted_entries(self, strategy_store) -> None:
        a1, a2 = _frozen_artifact_id(strategy_store), _frozen_artifact_id(strategy_store)
        strategy_store.append_angle_calibration_entry(AngleCalibrationEntry(
            angle_name="patchtst", artifact_id=a1, forecast_direction="long",
            actual_return_pct=0.03, directional_correct=True, brier_score=0.01,
        ))
        strategy_store.append_angle_calibration_entry(AngleCalibrationEntry(
            angle_name="patchtst", artifact_id=a2, forecast_direction="long",
            actual_return_pct=-0.01, directional_correct=False, brier_score=0.5,
        ))
        result = get_angle_calibration(strategy_store, "patchtst")
        assert result.n_entries == 2
        assert result.accuracy == 0.5

    def test_other_angles_do_not_bleed_in(self, strategy_store) -> None:
        strategy_store.append_angle_calibration_entry(AngleCalibrationEntry(
            angle_name="shock_personality", artifact_id=_frozen_artifact_id(strategy_store),
            forecast_direction="long", actual_return_pct=0.03, directional_correct=True, brier_score=0.01,
        ))
        result = get_angle_calibration(strategy_store, "patchtst")
        assert result.n_entries == 0
