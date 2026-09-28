from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.engine.sizing import (
    CompositeSizer,
    DEFAULT_DRAWDOWN_ACTION_SCALE,
    DEFAULT_REGIME_SCALE_MAP,
    DrawdownAwareSizer,
    EvidenceConfidenceSizer,
    FixedSizer,
    FractionalKellySizer,
    RegimeAwareSizer,
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

    def test_delegates_to_shared_kelly_fraction(self, monkeypatch):
        """Regression guard for the sizing-unification fix: this sizer must
        call vinu_infra.risk_math.kelly_fraction (the single source of truth
        also used by vinu-tools) rather than reimplementing the formula
        inline a second time."""
        import vinu_simulator.engine.sizing as sizing_module

        calls = []

        def _spy(win_rate, avg_win, avg_loss, fraction_of_kelly=1.0):
            calls.append((win_rate, avg_win, avg_loss, fraction_of_kelly))
            return 0.7

        monkeypatch.setattr(sizing_module, "_kelly_fraction", _spy)
        sizer = FractionalKellySizer(kelly_fraction=0.25, lookback_days=20, max_leverage=1.0)
        weights = np.array([1.0])
        history = np.array([0.02] * 16 + [-0.01] * 4)
        result = sizer.size(weights, history)
        assert len(calls) == 1
        assert result[0] == pytest.approx(0.7 * 0.25)


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

    def test_composite_model(self):
        sizer = build_position_sizer("composite", target_annual_vol=0.2, vol_lookback_days=10)
        assert isinstance(sizer, CompositeSizer)
        assert sizer.target_annual_vol == 0.2
        assert sizer.vol_lookback_days == 10

    def test_evidence_confidence_model(self):
        sizer = build_position_sizer(
            "evidence_confidence", evidence_min_confidence_scale=0.4, evidence_min_sample_size=3,
        )
        assert isinstance(sizer, EvidenceConfidenceSizer)
        assert sizer.min_confidence_scale == 0.4
        assert sizer.min_sample_size == 3

    def test_regime_aware_model(self):
        custom_map = {"bull": 1.2}
        sizer = build_position_sizer(
            "regime_aware", regime_scale_map=custom_map, regime_default_scale=0.3,
        )
        assert isinstance(sizer, RegimeAwareSizer)
        assert sizer.regime_scale_map == custom_map
        assert sizer.default_scale == 0.3

    def test_regime_aware_model_defaults_to_the_shared_scale_map(self):
        sizer = build_position_sizer("regime_aware")
        assert sizer.regime_scale_map == DEFAULT_REGIME_SCALE_MAP

    def test_drawdown_aware_model(self):
        sizer = build_position_sizer(
            "drawdown_aware", drawdown_threshold=-0.25, drawdown_halve_threshold=-0.12,
            drawdown_flat_threshold=-0.18, drawdown_abs_loss_threshold=-0.05,
        )
        assert isinstance(sizer, DrawdownAwareSizer)
        assert sizer.drawdown_threshold == -0.25
        assert sizer.halve_threshold == -0.12
        assert sizer.flat_threshold == -0.18
        assert sizer.abs_loss_threshold == -0.05

    def test_drawdown_aware_model_defaults_to_the_shared_action_scale_map(self):
        sizer = build_position_sizer("drawdown_aware")
        assert sizer.action_scale_map == DEFAULT_DRAWDOWN_ACTION_SCALE


def _correlated_symbol_returns(n_rows: int, n_symbols: int = 2, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    common = rng.normal(0.0005, 0.02, n_rows)
    data = {
        f"S{i}": common + rng.normal(0, 0.0005, n_rows)
        for i in range(n_symbols)
    }
    return pd.DataFrame(data)


def _uncorrelated_symbol_returns(n_rows: int, n_symbols: int = 2, seed: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {f"S{i}": rng.normal(0.0, 0.01, n_rows) for i in range(n_symbols)}
    return pd.DataFrame(data)


class TestCompositeSizer:
    def test_no_symbol_returns_falls_back_to_vol_target_only(self):
        sizer = CompositeSizer(target_annual_vol=0.15, vol_lookback_days=20, max_leverage=2.0)
        weights = np.array([1.0, 1.0])
        rng = np.random.default_rng(0)
        volatile_history = rng.normal(0, 0.05, 30)
        result = sizer.size(weights, volatile_history, symbol_returns=None)
        expected_vol_only = VolTargetSizer(
            target_annual_vol=0.15, lookback_days=20, max_leverage=2.0,
        ).size(weights, volatile_history)
        np.testing.assert_allclose(result, expected_vol_only)

    def test_single_symbol_returns_is_ignored_no_pairs_to_correlate(self):
        sizer = CompositeSizer(correlation_lookback_days=30)
        weights = np.array([1.0])
        history = np.full(30, 0.0)
        single_symbol = pd.DataFrame({"S0": np.full(60, 0.001)})
        result = sizer.size(weights, history, symbol_returns=single_symbol)
        # No vol scaling either (flat zero realized_returns -> max_leverage
        # branch), the point here is just that a single-column frame
        # never reaches the correlation math or crashes on it.
        assert np.isfinite(result).all()

    def test_insufficient_correlation_history_leaves_only_vol_scale_applied(self):
        sizer = CompositeSizer(correlation_lookback_days=60)
        weights = np.array([1.0, 1.0])
        history = np.full(30, 0.001)
        short_symbol_history = _correlated_symbol_returns(10)  # < 60 rows
        result = sizer.size(weights, history, symbol_returns=short_symbol_history)
        expected_vol_only = VolTargetSizer().size(weights, history)
        np.testing.assert_allclose(result, expected_vol_only)

    def test_highly_correlated_symbols_shrink_more_than_uncorrelated(self):
        weights = np.array([1.0, 1.0])
        history = np.full(30, 0.001)

        correlated_sizer = CompositeSizer(correlation_lookback_days=60, correlation_recompute_every=1)
        correlated = correlated_sizer.size(
            weights, history, symbol_returns=_correlated_symbol_returns(200),
        )

        uncorrelated_sizer = CompositeSizer(correlation_lookback_days=60, correlation_recompute_every=1)
        uncorrelated = uncorrelated_sizer.size(
            weights, history, symbol_returns=_uncorrelated_symbol_returns(200),
        )

        assert correlated[0] <= uncorrelated[0]

    def test_correlation_shrink_never_exceeds_max_correlation_shrink(self):
        sizer = CompositeSizer(
            correlation_lookback_days=60, correlation_recompute_every=1,
            max_correlation_shrink=0.4,
        )
        weights = np.array([1.0, 1.0])
        history = np.full(30, 0.001)
        result = sizer.size(weights, history, symbol_returns=_correlated_symbol_returns(200))
        vol_scale = VolTargetSizer().size(weights, history)[0]
        min_allowed = vol_scale * (1.0 - 0.4)
        assert result[0] >= min_allowed - 1e-9

    def test_correlation_factor_is_cached_between_recompute_intervals(self):
        sizer = CompositeSizer(correlation_lookback_days=60, correlation_recompute_every=100)
        weights = np.array([1.0, 1.0])
        history = np.full(30, 0.001)
        big_frame = _correlated_symbol_returns(300)

        first = sizer.size(weights, history, symbol_returns=big_frame.iloc[:200])
        # A different (uncorrelated) history one row later -- since it's
        # within the recompute interval, the cached scale must still be
        # used rather than recomputed from this new data.
        second = sizer.size(
            weights, history, symbol_returns=_uncorrelated_symbol_returns(201),
        )
        np.testing.assert_allclose(first, second)

    def test_never_flips_direction(self):
        sizer = CompositeSizer(correlation_lookback_days=60, correlation_recompute_every=1)
        weights = np.array([1.0, -1.0])
        history = np.full(30, 0.001)
        result = sizer.size(weights, history, symbol_returns=_correlated_symbol_returns(200))
        assert result[0] > 0
        assert result[1] < 0


def _resolved(trigger_time, outcome_recorded_at, return_at_horizon):
    return {
        "trigger_time": trigger_time,
        "outcome_recorded_at": outcome_recorded_at,
        "return_at_horizon": return_at_horizon,
    }


def _symbol_returns_columns(tickers: list[str], n_rows: int = 3) -> pd.DataFrame:
    return pd.DataFrame(np.zeros((n_rows, len(tickers))), columns=tickers)


class TestEvidenceConfidenceSizer:
    def test_missing_context_leaves_weights_unscaled(self):
        """item #4/#10: no symbol_returns, no current_date, or no
        evidence_triggers at all -- fail open, same posture every other
        sizer's own not-enough-context branch already uses."""
        sizer = EvidenceConfidenceSizer()
        weights = np.array([1.0, 1.0])
        history = np.full(10, 0.01)

        np.testing.assert_array_equal(sizer.size(weights, history), weights)
        np.testing.assert_array_equal(
            sizer.size(weights, history, symbol_returns=_symbol_returns_columns(["AAPL", "MSFT"])),
            weights,
        )

    def test_symbol_with_no_evidence_on_file_is_left_unscaled(self):
        sizer = EvidenceConfidenceSizer(min_sample_size=1)
        weights = np.array([1.0, 1.0])
        history = np.full(10, 0.01)

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL", "MSFT"]),
            current_date=pd.Timestamp("2026-09-10"),
            evidence_triggers={},
        )
        np.testing.assert_array_equal(result, weights)

    def test_symbol_below_min_sample_size_is_left_unscaled(self):
        sizer = EvidenceConfidenceSizer(min_sample_size=5)
        weights = np.array([1.0])
        history = np.full(10, 0.01)
        triggers = {
            "AAPL": [_resolved("2026-09-01T00:00:00+00:00", "2026-09-02T00:00:00+00:00", 0.02)],
        }

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL"]),
            current_date=pd.Timestamp("2026-09-10", tz="UTC"),
            evidence_triggers=triggers,
        )
        np.testing.assert_array_equal(result, weights)

    def test_strong_evidence_is_scaled_closer_to_full_size_than_weak_evidence(self):
        """`forecast_confidence_scale` only ever dampens (its ceiling is
        1.0, matching its own documented "a calm market/high conviction
        does not license extra leverage here" posture) -- so "strong
        evidence" means less shrunk, not boosted above the strategy's own
        weight."""
        sizer = EvidenceConfidenceSizer(min_sample_size=3, min_confidence_scale=0.5)
        weights = np.array([1.0])
        history = np.full(10, 0.01)
        # 5 of 5 winners -- Laplace-smoothed confidence = 6/7 ~= 0.857
        triggers = {
            "AAPL": [
                _resolved(f"2026-09-0{i}T00:00:00+00:00", f"2026-09-0{i + 1}T00:00:00+00:00", 0.02)
                for i in range(1, 6)
            ],
        }

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL"]),
            current_date=pd.Timestamp("2026-10-01", tz="UTC"),
            evidence_triggers=triggers,
        )
        assert result[0] == pytest.approx(6 / 7)
        assert result[0] <= 1.0

    def test_weak_evidence_scales_a_symbol_down_but_never_below_the_floor(self):
        sizer = EvidenceConfidenceSizer(min_sample_size=3, min_confidence_scale=0.5)
        weights = np.array([1.0])
        history = np.full(10, 0.01)
        # 0 of 5 winners -- Laplace-smoothed confidence = 1/7 ~= 0.143
        triggers = {
            "AAPL": [
                _resolved(f"2026-09-0{i}T00:00:00+00:00", f"2026-09-0{i + 1}T00:00:00+00:00", -0.02)
                for i in range(1, 6)
            ],
        }

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL"]),
            current_date=pd.Timestamp("2026-10-01", tz="UTC"),
            evidence_triggers=triggers,
        )
        assert result[0] == pytest.approx(0.5)  # floored, never scaled to zero

    def test_only_evidence_known_as_of_current_date_is_used(self):
        """Point-in-time safety: a trigger whose outcome was recorded
        AFTER current_date must not count -- that would be lookahead for
        a backtest replaying history."""
        sizer = EvidenceConfidenceSizer(min_sample_size=1)
        weights = np.array([1.0])
        history = np.full(10, 0.01)
        triggers = {
            "AAPL": [_resolved("2026-09-01T00:00:00+00:00", "2026-09-02T00:00:00+00:00", 0.02)],
        }

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL"]),
            current_date=pd.Timestamp("2020-01-01", tz="UTC"),  # well before the outcome
            evidence_triggers=triggers,
        )
        np.testing.assert_array_equal(result, weights)

    def test_scales_multiple_symbols_independently(self):
        sizer = EvidenceConfidenceSizer(min_sample_size=3, min_confidence_scale=0.5)
        weights = np.array([1.0, 1.0])
        history = np.full(10, 0.01)
        triggers = {
            "AAPL": [
                _resolved(f"2026-09-0{i}T00:00:00+00:00", f"2026-09-0{i + 1}T00:00:00+00:00", 0.02)
                for i in range(1, 6)
            ],
            # MSFT has no evidence at all -- must stay fully unscaled (1.0)
            # while AAPL is dampened toward its confidence's own factor.
        }

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL", "MSFT"]),
            current_date=pd.Timestamp("2026-10-01", tz="UTC"),
            evidence_triggers=triggers,
        )
        assert result[0] < 1.0
        assert result[1] == 1.0

    def test_never_flips_direction(self):
        sizer = EvidenceConfidenceSizer(min_sample_size=3)
        weights = np.array([1.0, -1.0])
        history = np.full(10, 0.01)
        triggers = {
            "AAPL": [
                _resolved(f"2026-09-0{i}T00:00:00+00:00", f"2026-09-0{i + 1}T00:00:00+00:00", 0.02)
                for i in range(1, 6)
            ],
            "MSFT": [
                _resolved(f"2026-09-0{i}T00:00:00+00:00", f"2026-09-0{i + 1}T00:00:00+00:00", 0.02)
                for i in range(1, 6)
            ],
        }

        result = sizer.size(
            weights, history,
            symbol_returns=_symbol_returns_columns(["AAPL", "MSFT"]),
            current_date=pd.Timestamp("2026-10-01", tz="UTC"),
            evidence_triggers=triggers,
        )
        assert result[0] > 0
        assert result[1] < 0


class TestRegimeAwareSizer:
    def test_no_regime_available_leaves_weights_unscaled(self):
        sizer = RegimeAwareSizer()
        weights = np.array([1.0, -1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime=None)

        np.testing.assert_array_equal(result, weights)

    def test_high_vol_regime_shrinks_the_portfolio(self):
        sizer = RegimeAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime="high_vol")

        assert result[0] == pytest.approx(DEFAULT_REGIME_SCALE_MAP["high_vol"])

    def test_bull_regime_uses_full_size_by_default(self):
        sizer = RegimeAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime="bull")

        assert result[0] == pytest.approx(1.0)

    def test_unknown_regime_label_falls_back_to_default_scale(self):
        sizer = RegimeAwareSizer(default_scale=0.25)
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime="some_new_label_not_in_the_map")

        assert result[0] == pytest.approx(0.25)

    def test_custom_scale_map_overrides_the_defaults(self):
        sizer = RegimeAwareSizer(regime_scale_map={"bear": 0.1})
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime="bear")

        assert result[0] == pytest.approx(0.1)

    def test_never_flips_direction(self):
        sizer = RegimeAwareSizer()
        weights = np.array([1.0, -1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime="high_vol")

        assert result[0] > 0
        assert result[1] < 0

    def test_scales_the_whole_portfolio_uniformly_not_per_symbol(self):
        """Unlike EvidenceConfidenceSizer, regime is a benchmark-level
        classification -- every symbol gets the same factor."""
        sizer = RegimeAwareSizer()
        weights = np.array([1.0, 2.0, 0.5])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, regime="bear")

        expected_scale = DEFAULT_REGIME_SCALE_MAP["bear"]
        np.testing.assert_allclose(result, weights * expected_scale)


class TestDrawdownAwareSizer:
    def test_no_portfolio_value_leaves_weights_unscaled(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0, -1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, portfolio_value=None)

        np.testing.assert_array_equal(result, weights)

    def test_first_call_establishes_peak_with_no_drawdown_yet(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        result = sizer.size(weights, history, portfolio_value=100_000.0)

        assert result[0] == pytest.approx(1.0)

    def test_halve_threshold_scales_by_half(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        result = sizer.size(weights, history, portfolio_value=89_000.0)  # -11%, past halve (-10%)

        assert result[0] == pytest.approx(0.5)

    def test_flat_threshold_scales_to_zero(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        result = sizer.size(weights, history, portfolio_value=84_000.0)  # -16%, past flat (-15%)

        assert result[0] == pytest.approx(0.0)

    def test_halt_threshold_scales_to_zero(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        result = sizer.size(weights, history, portfolio_value=79_000.0)  # -21%, past halt (-20%)

        assert result[0] == pytest.approx(0.0)

    def test_recovery_above_the_halt_threshold_is_not_sticky(self):
        """Confirmed design: halt is re-evaluated fresh every step, not
        latched -- a later recovery returns to whatever rung the ladder
        currently sits at, same as every other bar-by-bar sizer here."""
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        sizer.size(weights, history, portfolio_value=79_000.0)  # halt
        result = sizer.size(weights, history, portfolio_value=100_000.0)  # recovered

        assert result[0] == pytest.approx(1.0)

    def test_new_high_advances_the_tracked_peak(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        sizer.size(weights, history, portfolio_value=110_000.0)  # new peak
        # -11% from the NEW peak (110k), not the old one (100k) -- still
        # past halve (-10%) relative to 110k.
        result = sizer.size(weights, history, portfolio_value=97_500.0)

        assert result[0] == pytest.approx(0.5)

    def test_custom_action_scale_map_overrides_the_defaults(self):
        sizer = DrawdownAwareSizer(action_scale_map={"halve": 0.75})
        weights = np.array([1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        result = sizer.size(weights, history, portfolio_value=89_000.0)

        assert result[0] == pytest.approx(0.75)

    def test_never_flips_direction(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0, -1.0])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        result = sizer.size(weights, history, portfolio_value=89_000.0)

        assert result[0] > 0
        assert result[1] < 0

    def test_scales_the_whole_portfolio_uniformly_not_per_symbol(self):
        sizer = DrawdownAwareSizer()
        weights = np.array([1.0, 2.0, 0.5])
        history = np.full(10, 0.01)

        sizer.size(weights, history, portfolio_value=100_000.0)
        result = sizer.size(weights, history, portfolio_value=89_000.0)

        np.testing.assert_allclose(result, weights * 0.5)
