from __future__ import annotations

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.sweep_grid import sweep_evidence_verdict
from vinu_research.walk_forward import (
    WalkForwardConfig,
    WalkForwardRunResult,
    WindowSplitter,
    aggregate_metrics,
    deflated_sharpe_ratio,
    evaluate_walk_forward_stability,
    run_walk_forward,
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


class TestEvaluateWalkForwardStability:
    """Implementation-plan task 06: deterministic PASS/FAIL for a
    parameter-re-optimizing walk-forward pass, read by the recipe path's
    self-verdict alongside PBO."""

    def test_stable_pass_within_tolerance_passes(self):
        verdict = evaluate_walk_forward_stability(
            sharpe_gap=0.2,
            oos_positive_window_fraction=1.0,
            n_completed=3,
            n_planned=3,
            threshold=0.5,
            min_completed_windows=2,
        )
        assert verdict["passed"] is True
        assert verdict["reasons"] == ["walk-forward stability within tolerance"]

    def test_large_sharpe_gap_fails(self):
        verdict = evaluate_walk_forward_stability(
            sharpe_gap=0.9,
            oos_positive_window_fraction=1.0,
            n_completed=3,
            n_planned=3,
            threshold=0.5,
            min_completed_windows=2,
        )
        assert verdict["passed"] is False
        assert any("Sharpe gap 0.90 exceeds threshold 0.50" in r for r in verdict["reasons"])

    def test_threshold_is_configurable(self):
        # Same numbers as the "fails" case above, but a wider configured
        # threshold turns it into a pass -- the threshold must come from
        # config, not be hardcoded.
        verdict = evaluate_walk_forward_stability(
            sharpe_gap=0.9,
            oos_positive_window_fraction=1.0,
            n_completed=3,
            n_planned=3,
            threshold=1.0,
            min_completed_windows=2,
        )
        assert verdict["passed"] is True

    def test_incomplete_run_fails_closed(self):
        verdict = evaluate_walk_forward_stability(
            sharpe_gap=0.1,
            oos_positive_window_fraction=1.0,
            n_completed=2,
            n_planned=3,
            threshold=0.5,
            min_completed_windows=2,
        )
        assert verdict["passed"] is False
        assert any("incomplete walk-forward: 2/3 windows" in r for r in verdict["reasons"])

    def test_too_few_completed_windows_fails(self):
        verdict = evaluate_walk_forward_stability(
            sharpe_gap=0.1,
            oos_positive_window_fraction=1.0,
            n_completed=1,
            n_planned=3,
            threshold=0.5,
            min_completed_windows=2,
        )
        assert verdict["passed"] is False
        assert any("too few completed windows (1 < 2)" in r for r in verdict["reasons"])

    def test_mostly_losing_oos_windows_fails(self):
        verdict = evaluate_walk_forward_stability(
            sharpe_gap=0.1,
            oos_positive_window_fraction=0.33,
            n_completed=3,
            n_planned=3,
            threshold=0.5,
            min_completed_windows=2,
        )
        assert verdict["passed"] is False
        assert any("33% of out-of-sample windows had positive Sharpe" in r for r in verdict["reasons"])


class _FakeGrid:
    def __init__(self, ranked):
        self.ranked = ranked


class _FakeRanked:
    def __init__(self, params, metrics):
        self.params = params
        self.sweep_result = type("SweepResult", (), {"metrics": metrics})()


class _FakeCandidate:
    def __init__(self, metrics):
        self.metrics = metrics


def _run_wf_with(monkeypatch, window_params, is_sharpe, oos_sharpe, n_windows=3):
    """Drive run_walk_forward with a mocked sweep path: each window's grid
    re-optimization yields `window_params[i]` as the best params, and the
    out-of-sample backtest yields `oos_sharpe[i]`."""

    async def fake_run_sweep_grid(**kwargs):
        # Expanding windows share a common train START; match on the
        # distinct train END to identify the window.
        idx = 0
        for w in split_windows:
            if kwargs["to_date"] == w.train_end:
                idx = w.window_id
                break
        params = window_params[idx % len(window_params)]
        return _FakeGrid([_FakeRanked(params, {"sharpe_ratio": is_sharpe})])

    async def fake_run_sweep_candidate(**kwargs):
        return _FakeCandidate({"sharpe_ratio": oos_sharpe})

    monkeypatch.setattr("vinu_research.sweep_grid.run_sweep_grid", fake_run_sweep_grid)
    monkeypatch.setattr("vinu_research.sweep.run_sweep_candidate", fake_run_sweep_candidate)

    cfg = ResearchConfig(
        walk_forward_enabled=True,
        walk_forward_method="expanding",
        walk_forward_windows=n_windows,
        walk_forward_train_pct=0.6,
        walk_forward_test_pct=0.2,
        walk_forward_min_train_days=10,
        walk_forward_step_size_days=30,
        walk_forward_gap_days=5,
        walk_forward_stability_threshold=0.5,
        walk_forward_min_completed_windows=2,
    )
    splitter = WindowSplitter(WalkForwardConfig(
        method=cfg.walk_forward_method, n_windows=cfg.walk_forward_windows,
        train_pct=cfg.walk_forward_train_pct, test_pct=cfg.walk_forward_test_pct,
        min_train_days=cfg.walk_forward_min_train_days,
        step_size_days=cfg.walk_forward_step_size_days, gap_days=cfg.walk_forward_gap_days,
    ))
    global split_windows
    split_windows = splitter.split("2024-01-01", "2024-12-31")
    assert split_windows, "test needs at least one walk-forward window"

    import asyncio

    return asyncio.run(run_walk_forward(
        symbol="TEST",
        from_date="2024-01-01",
        to_date="2024-12-31",
        param_grid=[{"fast_period": 5}, {"fast_period": 10}],
        recipe="ma_cross",
        config=cfg,
        tools=object(),
    ))


class TestRunWalkForward:
    """The module-level parameter-re-optimizing walk-forward (task 06). Each
    window re-optimizes the grid on its train slice and backtests those
    params out-of-sample, reusing the exact same sweep execution path."""

    def test_stable_parameters_produce_a_pass_verdict(self, monkeypatch):
        params = [{"fast_period": 5}]  # identical optimal params every window
        result = _run_wf_with(monkeypatch, params, is_sharpe=1.4, oos_sharpe=1.1, n_windows=3)
        assert isinstance(result, WalkForwardRunResult)
        assert result.n_planned == 3
        assert result.n_completed == 3
        assert result.completeness == pytest.approx(1.0)
        assert result.parameter_agreement == pytest.approx(1.0)
        assert result.oos_positive_window_fraction == pytest.approx(1.0)
        assert result.stability_verdict["passed"] is True
        for w in result.windows:
            assert w.best_params == {"fast_period": 5}

    def test_unstable_parameters_collapse_oos_and_fail(self, monkeypatch):
        # Optimal params flip window to window AND out-of-sample Sharpe
        # collapses -- the signature of an overfit pick PBO can miss.
        params = [{"fast_period": 5}, {"fast_period": 10}, {"fast_period": 40}]
        result = _run_wf_with(monkeypatch, params, is_sharpe=1.8, oos_sharpe=-0.4, n_windows=3)
        assert result.parameter_agreement == pytest.approx(1 / 3)
        assert result.sharpe_gap == pytest.approx(1.8 - (-0.4), abs=0.05)
        assert result.oos_positive_window_fraction == 0.0
        assert result.stability_verdict["passed"] is False
        assert any("Sharpe gap" in r for r in result.stability_verdict["reasons"])
        assert any("0% of out-of-sample windows" in r for r in result.stability_verdict["reasons"])

    def test_partially_failed_windows_count_against_completeness(self, monkeypatch):
        # Only the first window finishes; completeness must reflect it and
        # the verdict must fail closed, not slip through on the lone win.
        async def fake_run_sweep_grid(**kwargs):
            if kwargs["to_date"] == split_windows[0].train_end:
                return _FakeGrid([_FakeRanked({"fast_period": 5}, {"sharpe_ratio": 1.5})])
            raise RuntimeError("simulated grid failure on later windows")

        async def fake_run_sweep_candidate(**kwargs):
            return _FakeCandidate({"sharpe_ratio": 1.2})

        monkeypatch.setattr("vinu_research.sweep_grid.run_sweep_grid", fake_run_sweep_grid)
        monkeypatch.setattr("vinu_research.sweep.run_sweep_candidate", fake_run_sweep_candidate)

        cfg = ResearchConfig(
            walk_forward_enabled=True,
            walk_forward_windows=3,
            walk_forward_train_pct=0.6,
            walk_forward_test_pct=0.2,
            walk_forward_min_train_days=10,
            walk_forward_step_size_days=30,
            walk_forward_gap_days=5,
            walk_forward_stability_threshold=0.5,
            walk_forward_min_completed_windows=2,
        )
        splitter = WindowSplitter(WalkForwardConfig(
            method="expanding", n_windows=3, train_pct=0.6, test_pct=0.2,
            min_train_days=10, step_size_days=30, gap_days=5,
        ))
        global split_windows
        split_windows = splitter.split("2024-01-01", "2024-12-31")
        assert len(split_windows) == 3

        import asyncio

        result = asyncio.run(run_walk_forward(
            symbol="TEST", from_date="2024-01-01", to_date="2024-12-31",
            param_grid=[{"fast_period": 5}], recipe="ma_cross",
            config=cfg, tools=object(),
        ))
        assert result.n_completed == 1
        assert result.completeness == pytest.approx(1 / 3)
        assert result.stability_verdict["passed"] is False
        assert any("1/3 windows completed" in r for r in result.stability_verdict["reasons"])

    def test_insufficient_data_returns_none(self, monkeypatch):
        cfg = ResearchConfig(
            walk_forward_enabled=True,
            walk_forward_windows=3,
            walk_forward_min_train_days=100000,
            walk_forward_stability_threshold=0.5,
        )
        import asyncio

        result = asyncio.run(run_walk_forward(
            symbol="TEST", from_date="2024-01-01", to_date="2024-12-31",
            param_grid=[{"fast_period": 5}], recipe="ma_cross",
            config=cfg, tools=object(),
        ))
        assert result is None


class TestSweepEvidenceVerdict:
    """The single deterministic gate the recipe-path self-verdict folds
    completeness + PBO + walk-forward stability into (task 06)."""

    def test_all_clean_signals_pass(self):
        verdict = sweep_evidence_verdict(
            completeness=1.0,
            pbo={"pbo": 0.3},
            walk_forward={"stability_verdict": {"passed": True, "reasons": []}},
        )
        assert verdict["passed"] is True

    def test_pbo_pass_but_walk_forward_fail_is_overall_fail(self):
        # The acceptance criterion for task 06: a candidate that passes PBO
        # yet fails walk-forward stability must NOT produce a pass.
        verdict = sweep_evidence_verdict(
            completeness=1.0,
            pbo={"pbo": 0.2},
            walk_forward={"stability_verdict": {"passed": False, "reasons": ["Sharpe gap 0.90 exceeds threshold 0.50"]}},
        )
        assert verdict["passed"] is False
        assert any("walk-forward stability verdict FAIL" in r for r in verdict["reasons"])

    def test_low_completeness_fails_even_with_clean_others(self):
        verdict = sweep_evidence_verdict(
            completeness=0.8,
            pbo={"pbo": 0.1},
            walk_forward={"stability_verdict": {"passed": True, "reasons": []}},
        )
        assert verdict["passed"] is False

    def test_severe_pbo_fails_even_with_clean_walk_forward(self):
        verdict = sweep_evidence_verdict(
            completeness=1.0,
            pbo={"pbo": 0.8},
            walk_forward={"stability_verdict": {"passed": True, "reasons": []}},
        )
        assert verdict["passed"] is False

    def test_missing_walk_forward_is_stated_not_silently_passed(self):
        verdict = sweep_evidence_verdict(
            completeness=1.0,
            pbo={"pbo": 0.2},
            walk_forward=None,
        )
        assert verdict["passed"] is False
        assert any("no walk-forward stability evidence" in r for r in verdict["reasons"])
