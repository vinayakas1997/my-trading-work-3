"""item #12 finding #3 (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): `pbo.py`'s CSCV math had no
direct unit tests -- only indirect coverage via `test_sweep_grid.py`
(checks `0.0 <= pbo <= 1.0` and nothing else). This feeds the promotion
gate's severe-overfitting check (`sweep_grid.py`'s `pbo_severe`,
`promotion.py`'s `promotion_pbo_threshold`), so a bug in the degenerate-
input fallback, the embargo boundary-dropping logic, or the Monte-Carlo
sampling branch could quietly let an overfit strategy get promoted.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from vinu_research.pbo import _logit, probability_of_backtest_overfitting


class TestDegenerateInputFallback:
    def test_too_few_periods_returns_coin_flip(self) -> None:
        result = probability_of_backtest_overfitting(np.zeros((4, 2)), n_splits=16)
        assert result == {
            "pbo": 0.5,
            "logit_mean": 0.0,
            "logit_std": 0.0,
            "n_splits": 16,
            "n_combinations": 0,
            "n_strategies": 2,
            "n_periods": 4,
        }

    def test_fewer_than_two_strategies_returns_coin_flip(self) -> None:
        result = probability_of_backtest_overfitting(np.zeros((64, 1)), n_splits=16)
        assert result["pbo"] == 0.5
        assert result["n_combinations"] == 0

    def test_exactly_at_the_period_boundary_does_not_fall_back(self) -> None:
        """T == n_splits * 2 is the smallest input that should run the
        real CSCV path, not the degenerate one."""
        rng = np.random.default_rng(0)
        mat = rng.normal(0, 1, (32, 2))
        result = probability_of_backtest_overfitting(mat, n_splits=16, rng=np.random.default_rng(1))
        assert result["n_combinations"] > 0


class TestRealSkillIsDetected:
    def test_a_dominant_strategy_gets_pbo_zero(self) -> None:
        """A strategy that's unambiguously best in every period stays
        the IS winner and the OOS winner in every single split -- PBO
        should be exactly 0, not just "low"."""
        rng = np.random.default_rng(1)
        T = 64
        matrix = np.column_stack(
            [
                np.full(T, 0.05) + rng.normal(0, 0.001, T),
                np.full(T, -0.02) + rng.normal(0, 0.001, T),
                np.full(T, -0.01) + rng.normal(0, 0.001, T),
            ]
        )
        result = probability_of_backtest_overfitting(matrix, n_splits=16, rng=np.random.default_rng(2))
        assert result["pbo"] == pytest.approx(0.0)
        assert result["n_strategies"] == 3
        assert result["n_periods"] == T

    def test_a_systematically_reversing_pair_gets_high_pbo(self) -> None:
        """Two strategies whose relative performance flips between the
        first and second half of the sample -- the classic "IS winner
        becomes OOS loser" overfitting shape -- should score meaningfully
        above the 0.5 coin-flip baseline, not just "some float in
        [0, 1]"."""
        n_splits = 16
        T = 64
        block_edges = np.linspace(0, T, n_splits + 1, dtype=int)
        matrix = np.zeros((T, 2))
        for i in range(n_splits):
            lo, hi = block_edges[i], block_edges[i + 1]
            if i < n_splits // 2:
                matrix[lo:hi, 0] = 1.0
                matrix[lo:hi, 1] = -1.0
            else:
                matrix[lo:hi, 0] = -1.0
                matrix[lo:hi, 1] = 1.0
        result = probability_of_backtest_overfitting(matrix, n_splits=n_splits, rng=np.random.default_rng(3))
        assert result["pbo"] > 0.5


class TestEmbargoBoundaryDropping:
    def test_embargo_actually_changes_the_result(self) -> None:
        """Regression guard for the embargo mechanism itself: a matrix
        with a large, boundary-localized leakage spike in every block
        must produce a different result with embargo_periods=1 than
        with 0 -- proving the "drop the leading period(s) of each OOS
        block" logic actually executes, not just that it's present in
        the source."""
        n_splits = 16
        T = 32
        rng = np.random.default_rng(42)
        matrix = rng.normal(0, 1, (T, 3))
        block_edges = np.linspace(0, T, n_splits + 1, dtype=int)
        for i in range(n_splits):
            lo = block_edges[i]
            matrix[lo] += rng.normal(0, 50, 3)

        no_embargo = probability_of_backtest_overfitting(
            matrix, n_splits=n_splits, embargo_periods=0, rng=np.random.default_rng(1)
        )
        with_embargo = probability_of_backtest_overfitting(
            matrix, n_splits=n_splits, embargo_periods=1, rng=np.random.default_rng(1)
        )
        assert no_embargo["logit_mean"] != pytest.approx(with_embargo["logit_mean"])
        assert with_embargo["embargo_periods"] == 1
        assert no_embargo["embargo_periods"] == 0

    def test_env_var_sets_embargo_when_param_is_not_positive(self) -> None:
        rng = np.random.default_rng(5)
        matrix = rng.normal(0, 1, (64, 2))
        old = os.environ.get("VINU_PBO_EMBARGO_PERIODS")
        try:
            os.environ["VINU_PBO_EMBARGO_PERIODS"] = "2"
            result = probability_of_backtest_overfitting(matrix, n_splits=16, rng=np.random.default_rng(6))
            assert result["embargo_periods"] == 2
        finally:
            if old is None:
                os.environ.pop("VINU_PBO_EMBARGO_PERIODS", None)
            else:
                os.environ["VINU_PBO_EMBARGO_PERIODS"] = old

    def test_malformed_env_var_falls_back_to_zero_without_crashing(self) -> None:
        rng = np.random.default_rng(7)
        matrix = rng.normal(0, 1, (64, 2))
        old = os.environ.get("VINU_PBO_EMBARGO_PERIODS")
        try:
            os.environ["VINU_PBO_EMBARGO_PERIODS"] = "notanint"
            result = probability_of_backtest_overfitting(matrix, n_splits=16, rng=np.random.default_rng(8))
            assert result["embargo_periods"] == 0
        finally:
            if old is None:
                os.environ.pop("VINU_PBO_EMBARGO_PERIODS", None)
            else:
                os.environ["VINU_PBO_EMBARGO_PERIODS"] = old

    def test_explicit_embargo_param_is_not_overridden_by_env_var(self) -> None:
        rng = np.random.default_rng(9)
        matrix = rng.normal(0, 1, (64, 2))
        old = os.environ.get("VINU_PBO_EMBARGO_PERIODS")
        try:
            os.environ["VINU_PBO_EMBARGO_PERIODS"] = "3"
            result = probability_of_backtest_overfitting(
                matrix, n_splits=16, embargo_periods=1, rng=np.random.default_rng(10)
            )
            assert result["embargo_periods"] == 1
        finally:
            if old is None:
                os.environ.pop("VINU_PBO_EMBARGO_PERIODS", None)
            else:
                os.environ["VINU_PBO_EMBARGO_PERIODS"] = old


class TestMonteCarloSampling:
    def test_n_combinations_caps_the_number_of_splits_evaluated(self) -> None:
        rng = np.random.default_rng(4)
        matrix = rng.normal(0, 1, (32, 3))
        result = probability_of_backtest_overfitting(
            matrix, n_splits=4, n_combinations=3, rng=np.random.default_rng(11)
        )
        assert result["n_combinations"] == 3
        assert 0.0 <= result["pbo"] <= 1.0

    def test_n_combinations_larger_than_all_splits_uses_all_of_them(self) -> None:
        rng = np.random.default_rng(4)
        matrix = rng.normal(0, 1, (32, 3))
        result = probability_of_backtest_overfitting(
            matrix, n_splits=4, n_combinations=1000, rng=np.random.default_rng(12)
        )
        assert result["n_combinations"] == 6  # C(4, 2)


class TestMeanMetric:
    def test_mean_metric_runs_without_error_and_returns_valid_pbo(self) -> None:
        rng = np.random.default_rng(13)
        matrix = rng.normal(0, 1, (64, 3))
        result = probability_of_backtest_overfitting(
            matrix, n_splits=16, metric="mean", rng=np.random.default_rng(14)
        )
        assert 0.0 <= result["pbo"] <= 1.0


class TestLogitClamping:
    def test_logit_at_zero_and_one_is_finite_not_inf(self) -> None:
        assert np.isfinite(_logit(0.0))
        assert np.isfinite(_logit(1.0))

    def test_logit_is_monotonic_and_zero_at_half(self) -> None:
        assert _logit(0.5) == pytest.approx(0.0, abs=1e-9)
        assert _logit(0.9) > _logit(0.5) > _logit(0.1)
