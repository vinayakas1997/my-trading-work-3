"""vinu_infra.risk_math is the single source of truth for position-sizing
scale factors shared by vinu-agent and vinu-live -- these pin the exact
formulas (especially vol_target_scale's annual->daily conversion) so the
two services can never silently re-diverge the way they had before."""

from __future__ import annotations

import pytest

from vinu_infra.risk_math import cvar_exceeds, forecast_confidence_scale, kelly_fraction, vol_target_scale


class TestVolTargetScale:
    def test_high_daily_vol_scales_size_down(self) -> None:
        # daily target = 0.15 / sqrt(252) ~= 0.009449; daily_vol 0.03 is ~3.17x
        scale = vol_target_scale(0.03, 0.15)
        expected = (0.15 / (252.0 ** 0.5)) / 0.03
        assert scale == expected

    def test_low_vol_never_scales_above_one(self) -> None:
        assert vol_target_scale(0.001, 0.15) == 1.0

    def test_non_positive_current_vol_is_fail_open(self) -> None:
        assert vol_target_scale(0.0, 0.15) == 1.0
        assert vol_target_scale(-0.01, 0.15) == 1.0

    def test_non_positive_target_vol_is_fail_open(self) -> None:
        assert vol_target_scale(0.03, 0.0) == 1.0

    def test_unparseable_current_vol_is_fail_open(self) -> None:
        assert vol_target_scale("not-a-number", 0.15) == 1.0
        assert vol_target_scale(None, 0.15) == 1.0

    def test_nan_or_inf_current_vol_is_fail_open(self) -> None:
        assert vol_target_scale(float("nan"), 0.15) == 1.0
        assert vol_target_scale(float("inf"), 0.15) == 1.0

    def test_nan_or_inf_target_vol_is_fail_open(self) -> None:
        assert vol_target_scale(0.03, float("nan")) == 1.0
        assert vol_target_scale(0.03, float("inf")) == 1.0

    def test_no_floor_below_0_25(self) -> None:
        # A prior vinu-agent-only copy floored this at 0.25x; the shared
        # implementation (matching vinu-live's live-path formula) does not.
        scale = vol_target_scale(1.0, 0.15)
        assert scale < 0.25


class TestForecastConfidenceScale:
    def test_confidence_within_bounds_passes_through(self) -> None:
        assert forecast_confidence_scale(0.8, floor=0.5) == 0.8

    def test_confidence_floored(self) -> None:
        assert forecast_confidence_scale(0.3, floor=0.5) == 0.5

    def test_confidence_capped_at_one(self) -> None:
        assert forecast_confidence_scale(1.5, floor=0.5) == 1.0

    def test_none_or_non_positive_is_fail_open(self) -> None:
        assert forecast_confidence_scale(None, floor=0.5) == 1.0
        assert forecast_confidence_scale(0.0, floor=0.5) == 1.0
        assert forecast_confidence_scale(-0.2, floor=0.5) == 1.0

    def test_nan_or_inf_is_fail_open(self) -> None:
        assert forecast_confidence_scale(float("nan"), floor=0.5) == 1.0
        assert forecast_confidence_scale(float("inf"), floor=0.5) == 1.0


class TestKellyFraction:
    def test_favorable_edge(self) -> None:
        # p=0.8, b=avg_win/avg_loss=2 -> f* = 0.8 - 0.2/2 = 0.7
        assert kelly_fraction(win_rate=0.8, avg_win=0.02, avg_loss=0.01) == pytest.approx(0.7)

    def test_unfavorable_edge_clips_to_zero(self) -> None:
        # p=0.2, b=0.5 -> f* = 0.2 - 0.8/0.5 = -1.4 -> clipped to 0.0
        assert kelly_fraction(win_rate=0.2, avg_win=0.01, avg_loss=0.02) == 0.0

    def test_fraction_of_kelly_scales_result(self) -> None:
        full = kelly_fraction(win_rate=0.8, avg_win=0.02, avg_loss=0.01, fraction_of_kelly=1.0)
        quarter = kelly_fraction(win_rate=0.8, avg_win=0.02, avg_loss=0.01, fraction_of_kelly=0.25)
        assert quarter == full * 0.25

    def test_non_positive_avg_loss_returns_zero(self) -> None:
        assert kelly_fraction(win_rate=0.6, avg_win=0.02, avg_loss=0.0) == 0.0
        assert kelly_fraction(win_rate=0.6, avg_win=0.02, avg_loss=-0.01) == 0.0

    def test_non_positive_avg_win_returns_zero_not_zerodivisionerror(self) -> None:
        # avg_win=0 previously fell through to b = avg_win/avg_loss = 0.0,
        # then (p*b - q)/b raised ZeroDivisionError -- discovered when
        # vinu-agent's full_kelly_fraction (a payoff_ratio<=0 input) was
        # unified onto this shared function.
        assert kelly_fraction(win_rate=0.6, avg_win=0.0, avg_loss=1.0) == 0.0
        assert kelly_fraction(win_rate=0.6, avg_win=-0.5, avg_loss=1.0) == 0.0

    def test_win_rate_outside_open_interval_returns_zero(self) -> None:
        assert kelly_fraction(win_rate=0.0, avg_win=0.02, avg_loss=0.01) == 0.0
        assert kelly_fraction(win_rate=1.0, avg_win=0.02, avg_loss=0.01) == 0.0


class TestCvarExceeds:
    def test_above_threshold(self) -> None:
        assert cvar_exceeds(0.05, 0.03) is True

    def test_below_threshold(self) -> None:
        assert cvar_exceeds(0.02, 0.03) is False

    def test_unparseable_is_fail_open(self) -> None:
        assert cvar_exceeds("bad", 0.03) is False
        assert cvar_exceeds(None, 0.03) is False

    def test_nan_or_inf_is_fail_open(self) -> None:
        # float('nan') > threshold is always False in Python regardless --
        # this pins that as deliberate (same fail-open convention as every
        # other garbage-input case here), not an accident of the raw
        # comparison, and also covers +inf explicitly.
        assert cvar_exceeds(float("nan"), 0.03) is False
        assert cvar_exceeds(float("inf"), 0.03) is False
