from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_simulator.engine.validation import (
    block_bootstrap_permutation,
    bootstrap_sharpe_ci,
    compute_validation_verdict,
    monte_carlo_permutation,
    price_path_resample,
    walk_forward_consistency,
)


class TestBlockBootstrapPermutation:
    def test_returns_expected_keys_with_sufficient_data(self):
        pnls = [1.0, -0.5, 0.8, -0.3, 1.2, -0.7, 0.5, -0.2, 0.9, -0.4]
        result = block_bootstrap_permutation(pnls, actual_sharpe=0.5, n_iterations=50)
        assert "p_value" in result
        assert "sim_mean" in result
        assert "sim_std" in result
        assert result["n_trades"] == 10
        assert result["minimum_met"] is True
        assert result["block_size"] == 5

    def test_requires_minimum_trades(self):
        result = block_bootstrap_permutation([1.0, -0.5], 0.5)
        assert result["minimum_met"] is False
        assert result["p_value"] == 1.0

    def test_handles_single_trade(self):
        result = block_bootstrap_permutation([1.0], 0.5)
        assert result["minimum_met"] is False

    def test_handles_empty_trades(self):
        result = block_bootstrap_permutation([], 0.5)
        assert result["minimum_met"] is False

    def test_handles_block_size_one(self):
        pnls = [1.0, -0.5, 0.8]
        result = block_bootstrap_permutation(pnls, actual_sharpe=0.5, block_size=1, n_iterations=50)
        assert result["minimum_met"] is True
        assert "p_value" in result

    def test_uses_provided_rng(self):
        pnls = [1.0, -0.5, 0.8, -0.3, 1.2] * 5
        rng = np.random.default_rng(42)
        r1 = block_bootstrap_permutation(pnls, 0.5, n_iterations=50, rng=rng)
        rng = np.random.default_rng(42)
        r2 = block_bootstrap_permutation(pnls, 0.5, n_iterations=50, rng=rng)
        assert r1["p_value"] == r2["p_value"]


class TestPricePathResample:
    def test_returns_expected_keys_with_sufficient_data(self):
        returns = pd.Series(np.random.default_rng(42).normal(0.001, 0.02, 100))
        result = price_path_resample(returns, actual_sharpe=0.5, n_iterations=50)
        assert "p_value" in result
        assert "sim_mean" in result
        assert "sim_std" in result
        assert result["n_observations"] == 100
        assert result["minimum_met"] is True
        assert result["block_size"] == 20

    def test_requires_sufficient_observations(self):
        returns = pd.Series(np.random.default_rng(42).normal(0.001, 0.02, 10))
        result = price_path_resample(returns, actual_sharpe=0.5, block_size=20)
        assert result["minimum_met"] is False
        assert result["p_value"] == 1.0

    def test_near_zero_sharpe_produces_high_p_value(self):
        rng = np.random.default_rng(42)
        returns = pd.Series(rng.normal(0.0, 0.02, 500))
        result = price_path_resample(returns, actual_sharpe=0.05, n_iterations=100)
        assert result["p_value"] > 0.05

    def test_uses_provided_rng(self):
        returns = pd.Series(np.random.default_rng(42).normal(0.001, 0.02, 200))
        rng = np.random.default_rng(99)
        r1 = price_path_resample(returns, 0.5, n_iterations=50, rng=rng)
        rng = np.random.default_rng(99)
        r2 = price_path_resample(returns, 0.5, n_iterations=50, rng=rng)
        assert r1["p_value"] == r2["p_value"]


class TestComputeValidationVerdict:
    def test_passes_when_all_sub_checks_pass(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.02},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is True
        assert len(verdict["reasons"]) == 5
        assert all("PASS" in r for r in verdict["reasons"])

    def test_fails_when_monte_carlo_p_value_is_high(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.10},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.02},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is False
        assert any("FAIL" in r for r in verdict["reasons"])

    def test_fails_when_block_bootstrap_p_value_is_high(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.10},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is False

    def test_fails_when_price_path_p_value_is_high(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.02},
            "price_path": {"minimum_met": True, "p_value": 0.15},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is False

    def test_fails_when_walk_forward_consistency_is_low(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.02},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.40},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is False

    def test_fails_when_bootstrap_ci_lower_bound_is_negative(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.02},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": -0.01},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is False

    def test_skips_missing_sub_results(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is True
        assert any("skipped" in r for r in verdict["reasons"])

    def test_fails_closed_when_every_method_has_insufficient_data(self):
        # A strategy with too few trades/observations for any method to run must
        # NOT silently pass a gate that's supposed to be un-bypassable — fail closed.
        validation = {
            "monte_carlo": {"minimum_met": False, "p_value": 1.0},
            "block_bootstrap": {"minimum_met": False, "p_value": 1.0},
            "price_path": {"minimum_met": False, "p_value": 1.0},
            "walk_forward": {"minimum_met": False, "consistency_rate": 0.0},
            "bootstrap": {"minimum_met": False, "ci_low": 0.0},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is False
        assert all("skipped" in r for r in verdict["reasons"][:-1])
        assert "sufficient data" in verdict["reasons"][-1].lower()

    def test_passes_when_some_methods_skip_but_the_rest_pass(self):
        # Partial data (e.g. too few trades for block-bootstrap but enough for
        # everything else) should not itself block a strategy that otherwise
        # clears every check that *could* run.
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": False, "p_value": 1.0},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        verdict = compute_validation_verdict(validation)
        assert verdict["passed"] is True
        assert any("skipped" in r for r in verdict["reasons"])

    def test_threshold_boundary_monte_carlo(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.0499},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.01},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        assert compute_validation_verdict(validation)["passed"] is True

    def test_threshold_boundary_monte_carlo_fails(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.0501},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.01},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        assert compute_validation_verdict(validation)["passed"] is False

    def test_threshold_boundary_consistency_just_below(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.01},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.599},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        assert compute_validation_verdict(validation)["passed"] is False

    def test_threshold_boundary_consistency_just_above(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.01},
            "price_path": {"minimum_met": True, "p_value": 0.05},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.601},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        assert compute_validation_verdict(validation)["passed"] is True

    def test_threshold_boundary_price_path(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.01},
            "price_path": {"minimum_met": True, "p_value": 0.099},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        assert compute_validation_verdict(validation)["passed"] is True

    def test_threshold_boundary_price_path_fails(self):
        validation = {
            "monte_carlo": {"minimum_met": True, "p_value": 0.01},
            "block_bootstrap": {"minimum_met": True, "p_value": 0.01},
            "price_path": {"minimum_met": True, "p_value": 0.101},
            "walk_forward": {"minimum_met": True, "consistency_rate": 0.75},
            "bootstrap": {"minimum_met": True, "ci_low": 0.02},
        }
        assert compute_validation_verdict(validation)["passed"] is False
