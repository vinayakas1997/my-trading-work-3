from __future__ import annotations

import pytest

from vinu_research.walk_forward import (
    WalkForwardConfig,
    WindowSplitter,
    aggregate_metrics,
    deflated_sharpe_ratio,
)


class TestWindowSplitter:
    def test_expanding_returns_correct_number_of_windows(self):
        config = WalkForwardConfig(
            method="expanding",
            n_windows=3,
            min_train_days=10,
            step_size_days=30,
            gap_days=5,
            train_pct=0.6,
            test_pct=0.2,
        )
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-12-31")
        assert len(windows) == 3

    def test_sliding_returns_correct_number_of_windows(self):
        config = WalkForwardConfig(
            method="sliding",
            n_windows=3,
            min_train_days=10,
            step_size_days=30,
            gap_days=5,
            train_pct=0.6,
            test_pct=0.2,
        )
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-12-31")
        assert len(windows) > 0

    def test_returns_empty_for_insufficient_data(self):
        config = WalkForwardConfig(
            n_windows=3,
            min_train_days=1000,
            train_pct=0.6,
            test_pct=0.2,
        )
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-03-01")
        assert len(windows) == 0

    def test_returns_empty_for_extreme_test_pct_underflow(self):
        config = WalkForwardConfig(
            n_windows=3,
            min_train_days=10,
            test_pct=0.9,
        )
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-03-01")
        assert len(windows) == 0

    def test_expanding_train_start_is_always_from_date(self):
        config = WalkForwardConfig(
            method="expanding",
            n_windows=2,
            min_train_days=10,
            step_size_days=30,
            gap_days=5,
            train_pct=0.5,
            test_pct=0.2,
        )
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-12-31")
        for w in windows:
            assert w.train_start == "2024-01-01"

    def test_windows_have_gap_between_train_and_test(self):
        config = WalkForwardConfig(
            method="sliding",
            n_windows=2,
            min_train_days=10,
            step_size_days=30,
            gap_days=5,
            train_pct=0.5,
            test_pct=0.2,
        )
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-12-31")
        for w in windows:
            from datetime import datetime
            train_end = datetime.strptime(w.train_end, "%Y-%m-%d")
            test_start = datetime.strptime(w.test_start, "%Y-%m-%d")
            assert (test_start - train_end).days >= 5

    def test_window_ids_are_sequential(self):
        config = WalkForwardConfig(n_windows=5, min_train_days=10, step_size_days=20)
        splitter = WindowSplitter(config)
        windows = splitter.split("2024-01-01", "2024-12-31")
        for i, w in enumerate(windows, 1):
            assert w.window_id == i


class TestAggregateMetrics:
    def test_returns_median_values(self):
        is_list = [
            {"sharpe_ratio": 1.0, "max_drawdown": -0.1},
            {"sharpe_ratio": 2.0, "max_drawdown": -0.2},
            {"sharpe_ratio": 3.0, "max_drawdown": -0.3},
        ]
        oos_list = [
            {"sharpe_ratio": 0.8, "max_drawdown": -0.12},
            {"sharpe_ratio": 1.5, "max_drawdown": -0.18},
            {"sharpe_ratio": 2.2, "max_drawdown": -0.25},
        ]
        is_agg, oos_agg = aggregate_metrics(is_list, oos_list)

        assert is_agg["sharpe_ratio"] == 2.0
        assert is_agg["max_drawdown"] == -0.2
        assert oos_agg["sharpe_ratio"] == 1.5
        assert oos_agg["max_drawdown"] == -0.18

    def test_returns_empty_for_empty_input(self):
        is_agg, oos_agg = aggregate_metrics([], [])
        assert is_agg == {}
        assert oos_agg == {}


class TestWalkForwardConfig:
    def test_default_config(self):
        config = WalkForwardConfig()
        assert config.method == "expanding"
        assert config.n_windows == 3
        assert config.train_pct == 0.6
        assert config.test_pct == 0.2
        assert config.gap_days == 5
        assert config.min_train_days == 252

    def test_custom_config(self):
        config = WalkForwardConfig(
            method="sliding",
            n_windows=5,
            train_pct=0.7,
            gap_days=10,
        )
        assert config.method == "sliding"
        assert config.n_windows == 5
        assert config.train_pct == 0.7
        assert config.gap_days == 10


class TestDeflatedSharpeRatio:
    def test_single_trial_matches_plain_significance(self):
        # With n_trials=1, DSR should behave like an ordinary significance test —
        # a strongly positive Sharpe over many observations should look genuine.
        dsr = deflated_sharpe_ratio(sharpe=1.5, n_trials=1, n_obs=252)
        assert dsr > 0.9

    def test_more_trials_deflates_the_same_sharpe(self):
        # The same observed Sharpe should look less impressive as more independent
        # trials were run to find it — that's the entire point of the correction.
        # Sharpe/n_obs chosen so neither case saturates to float 1.0.
        few_trials = deflated_sharpe_ratio(sharpe=0.3, n_trials=1, n_obs=100)
        many_trials = deflated_sharpe_ratio(sharpe=0.3, n_trials=50, n_obs=100)
        assert many_trials < few_trials

    def test_more_observations_increases_confidence(self):
        short_sample = deflated_sharpe_ratio(sharpe=1.0, n_trials=5, n_obs=60)
        long_sample = deflated_sharpe_ratio(sharpe=1.0, n_trials=5, n_obs=1000)
        assert long_sample > short_sample

    def test_zero_sharpe_is_never_confidently_skillful(self):
        dsr = deflated_sharpe_ratio(sharpe=0.0, n_trials=10, n_obs=252)
        assert dsr < 0.5

    def test_degenerate_inputs_return_neutral_probability(self):
        assert deflated_sharpe_ratio(sharpe=1.0, n_trials=0, n_obs=252) == 0.5
        assert deflated_sharpe_ratio(sharpe=1.0, n_trials=5, n_obs=1) == 0.5

    def test_output_is_a_valid_probability(self):
        for sharpe in (-2.0, -0.5, 0.0, 0.5, 1.0, 2.0, 5.0):
            dsr = deflated_sharpe_ratio(sharpe=sharpe, n_trials=15, n_obs=252)
            assert 0.0 <= dsr <= 1.0


class TestAggregateMetricsDispersion:
    def test_reports_std_and_losing_window_fraction(self):
        is_list = [{"sharpe_ratio": 1.0, "total_return": 0.1}, {"sharpe_ratio": 1.2, "total_return": 0.2}]
        oos_list = [
            {"sharpe_ratio": 0.5, "total_return": 0.05},
            {"sharpe_ratio": -0.3, "total_return": -0.10},
            {"sharpe_ratio": 0.8, "total_return": 0.08},
        ]
        is_agg, oos_agg = aggregate_metrics(is_list, oos_list)
        assert "sharpe_ratio_std" in is_agg
        assert "sharpe_ratio_std" in oos_agg
        assert oos_agg["losing_window_fraction"] == pytest.approx(1 / 3)
