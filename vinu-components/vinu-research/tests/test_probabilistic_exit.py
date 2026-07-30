from __future__ import annotations

import pytest

from vinu_research.probabilistic_exit import confidence_decay, get_exit_action, probability_of_failure


class TestConfidenceDecay:
    def test_no_decay_when_zero_days_elapsed(self) -> None:
        assert confidence_decay(1.0, 30, 0) == 1.0

    def test_decay_to_about_half_at_half_life(self) -> None:
        result = confidence_decay(1.0, 30, 10)
        assert 0.45 < result < 0.55

    def test_decay_to_about_12pct_at_horizon(self) -> None:
        result = confidence_decay(1.0, 30, 30)
        assert 0.10 < result < 0.15

    def test_no_decay_when_horizon_is_zero(self) -> None:
        assert confidence_decay(0.8, 0, 10) == 0.8

    def test_lower_initial_confidence(self) -> None:
        result = confidence_decay(0.5, 20, 10)
        assert result < 0.3 and result > 0.1


class TestProbabilityOfFailure:
    def test_low_failure_when_strong_calibration_and_no_price_move(self) -> None:
        p = probability_of_failure(cal_accuracy=0.9, horizon_days=30)
        assert p < 0.3

    def test_high_failure_when_wrong_calibration_and_price_moved(self) -> None:
        p = probability_of_failure(cal_accuracy=0.4, price_distance_std=2.0, magnitude_std=1.0, horizon_days=30, days_elapsed=25)
        assert p > 0.6

    def test_no_calibration_defaults_to_coinflip(self) -> None:
        p = probability_of_failure(horizon_days=30)
        assert p == 0.4

    def test_price_weight_increases_when_move_exceeds_one_std(self) -> None:
        p_small = probability_of_failure(0.5, 0.5, 1.0, 0.5, 30, 0)
        p_large = probability_of_failure(0.5, 1.5, 1.0, 0.5, 30, 0)
        assert p_large > p_small

    def test_day_zero_fresh_forecast(self) -> None:
        p = probability_of_failure(cal_accuracy=0.6, horizon_days=30, days_elapsed=0)
        assert 0.3 <= p <= 0.5

    def test_stale_forecast_raises_failure(self) -> None:
        p_fresh = probability_of_failure(cal_accuracy=0.5, initial_confidence=0.8, horizon_days=10, days_elapsed=0)
        p_stale = probability_of_failure(cal_accuracy=0.5, initial_confidence=0.8, horizon_days=10, days_elapsed=10)
        assert p_stale > p_fresh

    def test_clamps_to_zero_one(self) -> None:
        p = probability_of_failure(cal_accuracy=0.0, price_distance_std=99.0, magnitude_std=1.0, horizon_days=1, days_elapsed=100)
        assert 0.0 <= p <= 1.0


class TestGetExitAction:
    def test_monitor_below_0_3(self) -> None:
        assert get_exit_action(0.2)["action"] == "monitor"

    def test_trim_at_0_3(self) -> None:
        assert get_exit_action(0.3)["action"] == "trim"

    def test_exit_at_0_4(self) -> None:
        assert get_exit_action(0.4)["action"] == "exit"

    def test_hard_exit_at_0_6(self) -> None:
        assert get_exit_action(0.6)["action"] == "hard_exit"
