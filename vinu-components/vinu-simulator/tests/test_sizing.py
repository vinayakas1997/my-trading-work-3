from __future__ import annotations

import numpy as np
import pytest

from vinu_simulator.engine.sizing import (
    FixedSizer,
    FractionalKellySizer,
    VolTargetSizer,
    build_position_sizer,
)


class TestFixedSizer:
    def test_returns_weights_unchanged(self):
        sizer = FixedSizer()
        weights = np.array([0.5, -0.3, 0.2])
        result = sizer.size(weights, np.array([0.01, -0.02, 0.015]))
        np.testing.assert_array_equal(result, weights)


class TestVolTargetSizer:
    def test_insufficient_history_leaves_weights_unadjusted(self):
        sizer = VolTargetSizer(lookback_days=20)
        weights = np.array([1.0])
        short_history = np.full(5, 0.01)  # fewer than lookback_days
        result = sizer.size(weights, short_history)
        np.testing.assert_array_equal(result, weights)

    def test_high_realized_vol_shrinks_exposure(self):
        sizer = VolTargetSizer(target_annual_vol=0.15, lookback_days=20, max_leverage=2.0)
        weights = np.array([1.0])
        # Large daily swings -> high realized vol -> should scale down well below 1.0
        rng = np.random.default_rng(0)
        volatile_history = rng.normal(0, 0.05, 30)  # ~79% annualized vol
        result = sizer.size(weights, volatile_history)
        assert result[0] < 0.5

    def test_low_realized_vol_scales_up_toward_max_leverage(self):
        sizer = VolTargetSizer(target_annual_vol=0.15, lookback_days=20, max_leverage=3.0)
        weights = np.array([1.0])
        calm_history = np.full(30, 0.0005)  # near-zero variance -> vol ~0
        result = sizer.size(weights, calm_history)
        assert result[0] == pytest.approx(3.0)  # clipped at max_leverage

    def test_direction_is_preserved_not_flipped(self):
        sizer = VolTargetSizer(lookback_days=20)
        weights = np.array([-0.8, 0.6])
        history = np.full(30, 0.001)
        result = sizer.size(weights, history)
        assert result[0] < 0  # still short
        assert result[1] > 0  # still long

    def test_zero_vol_and_zero_target_does_not_crash(self):
        sizer = VolTargetSizer(target_annual_vol=0.0, lookback_days=5, max_leverage=1.0)
        weights = np.array([1.0])
        history = np.zeros(10)
        result = sizer.size(weights, history)
        assert np.isfinite(result).all()


class TestFractionalKellySizer:
    def test_insufficient_history_leaves_weights_unadjusted(self):
        sizer = FractionalKellySizer(lookback_days=60)
        weights = np.array([1.0])
        result = sizer.size(weights, np.full(10, 0.01))
        np.testing.assert_array_equal(result, weights)

    def test_all_wins_or_all_losses_leaves_weights_unadjusted(self):
        sizer = FractionalKellySizer(lookback_days=10)
        weights = np.array([1.0])
        all_wins = np.full(10, 0.01)
        result = sizer.size(weights, all_wins)
        np.testing.assert_array_equal(result, weights)

    def test_strong_favorable_edge_scales_up_toward_kelly_fraction_cap(self):
        sizer = FractionalKellySizer(kelly_fraction=0.25, lookback_days=20, max_leverage=1.0)
        weights = np.array([1.0])
        # 80% win rate, wins twice as large as losses -> strongly favorable edge
        history = np.array([0.02] * 16 + [-0.01] * 4)
        result = sizer.size(weights, history)
        # kelly = 0.8 - 0.2/2 = 0.7; scale = min(0.7*0.25, 1.0) = 0.175
        assert result[0] == pytest.approx(0.175, abs=1e-6)

    def test_unfavorable_edge_scales_toward_zero(self):
        sizer = FractionalKellySizer(kelly_fraction=0.25, lookback_days=20)
        weights = np.array([1.0])
        # 20% win rate, wins smaller than losses -> unfavorable edge
        history = np.array([0.01] * 4 + [-0.02] * 16)
        result = sizer.size(weights, history)
        assert result[0] == pytest.approx(0.0, abs=1e-9)

    def test_never_flips_direction(self):
        sizer = FractionalKellySizer(kelly_fraction=0.25, lookback_days=20)
        weights = np.array([-1.0])
        history = np.array([0.01] * 4 + [-0.02] * 16)  # unfavorable -> kelly clipped to 0
        result = sizer.size(weights, history)
        assert result[0] <= 0  # scaled toward zero, never becomes positive


class TestBuildPositionSizer:
    def test_fixed_model(self):
        assert isinstance(build_position_sizer("fixed"), FixedSizer)

    def test_vol_target_model(self):
        sizer = build_position_sizer("vol_target", target_annual_vol=0.2, vol_lookback_days=10)
        assert isinstance(sizer, VolTargetSizer)
        assert sizer.target_annual_vol == 0.2
        assert sizer.lookback_days == 10

    def test_kelly_model(self):
        sizer = build_position_sizer("kelly", kelly_fraction=0.5, kelly_lookback_days=30)
        assert isinstance(sizer, FractionalKellySizer)
        assert sizer.kelly_fraction == 0.5
        assert sizer.lookback_days == 30

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown position_sizing_model"):
            build_position_sizer("not_a_real_model")
