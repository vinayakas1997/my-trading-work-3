from __future__ import annotations

from vinu_research.calibration import CalibrationGate, CalibrationTracker
from vinu_research.forecast_skill import ForecastSkillConfig
from vinu_research.models import Forecast


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
