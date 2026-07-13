from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_research.benchmark import (
    _geometric_cagr,
    compute_benchmark_comparison,
    compute_benchmark_returns_metrics,
)
from vinu_research.models import BacktestMetrics, BacktestResult

_BENCHMARK_RULES_FALLBACK_ALPHA_CUTOFF = 0.0
_BENCHMARK_RULES_FALLBACK_IR_CUTOFF = 0.5
_BENCHMARK_RULES_FALLBACK_DOWN_CAPTURE_CUTOFF = 1.2


def _check_benchmark_rules(
    result: BacktestResult,
) -> list[str]:
    """Replicate the benchmark rule logic from loop.py _rule_based_check
    to test in isolation without importing loop module."""
    suggestions: list[str] = []
    m = result.metrics

    if result.benchmark_metrics:
        for bm_name, bm_data in result.benchmark_metrics.items():
            bm_cagr = bm_data.get("cagr", 0)
            bm_alpha = bm_data.get("alpha", None)
            bm_ir = bm_data.get("information_ratio", None)
            bm_down = bm_data.get("down_capture", None)
            bm_excess_cagr = bm_data.get("excess_cagr", None)

            if bm_alpha is not None and bm_alpha < _BENCHMARK_RULES_FALLBACK_ALPHA_CUTOFF:
                suggestions.append(
                    f"Alpha is {bm_alpha:.1%} vs {bm_name} — "
                    "strategy is destroying value relative to benchmark"
                )

            if bm_ir is not None and 0 < bm_ir < _BENCHMARK_RULES_FALLBACK_IR_CUTOFF:
                suggestions.append(
                    f"Information ratio {bm_ir:.2f} vs {bm_name} — "
                    "active returns do not justify tracking error"
                )

            if bm_down is not None and bm_down > _BENCHMARK_RULES_FALLBACK_DOWN_CAPTURE_CUTOFF:
                suggestions.append(
                    f"Down capture {bm_down:.0%} vs {bm_name} — "
                    "strategy falls more than market in downturns. Add tail protection"
                )

            if bm_excess_cagr is not None and bm_excess_cagr < 0:
                suggestions.append(
                    f"CAGR below {bm_name} benchmark — "
                    "consider if active management is justified"
                )
            elif bm_alpha is None and bm_cagr > m.cagr:
                suggestions.append(
                    f"Benchmark {bm_name} CAGR ({bm_cagr:.1%}) exceeds strategy ({m.cagr:.1%}) — "
                    "simpler passive approach may outperform"
                )

    return suggestions


def _make_returns(annual_sharpe: float, n: int = 252, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    daily_vol = 0.01
    daily_mean = annual_sharpe * daily_vol / np.sqrt(252)
    return pd.Series(rng.normal(daily_mean, daily_vol, n))


def _make_benchmark_metrics(
    sharpe: float = 1.0,
    cagr: float = 0.1,
    **overrides,
) -> dict[str, float]:
    m = {
        "total_return": 0.15,
        "cagr": cagr,
        "annual_volatility": 0.15,
        "sharpe_ratio": sharpe,
        "max_drawdown": -0.10,
        "win_rate": 0.55,
        "sortino_ratio": 1.0,
    }
    m.update(overrides)
    return m


class TestComputeBenchmarkReturnsMetrics:
    def test_returns_dict_with_expected_keys(self):
        rets = _make_returns(1.0, 252)
        result = compute_benchmark_returns_metrics(rets)
        expected_keys = {"total_return", "cagr", "annual_volatility", "sharpe_ratio", "max_drawdown", "win_rate", "sortino_ratio"}
        assert expected_keys.issubset(result.keys())

    def test_positive_sharpe_gives_positive_sharpe_ratio(self):
        rets = _make_returns(1.5, 252)
        result = compute_benchmark_returns_metrics(rets)
        assert result["sharpe_ratio"] > 0

    def test_negative_sharpe_gives_negative_sharpe_ratio(self):
        rets = _make_returns(-0.5, 252)
        result = compute_benchmark_returns_metrics(rets)
        assert result["sharpe_ratio"] < 0

    def test_returns_empty_dict_for_insufficient_data(self):
        rets = pd.Series([0.01])
        result = compute_benchmark_returns_metrics(rets)
        assert result == {}

    def test_max_drawdown_is_negative_or_zero(self):
        rets = _make_returns(0.8, 252)
        result = compute_benchmark_returns_metrics(rets)
        assert result["max_drawdown"] <= 0

    def test_win_rate_between_0_and_1(self):
        rets = _make_returns(1.0, 252)
        result = compute_benchmark_returns_metrics(rets)
        assert 0 <= result["win_rate"] <= 1

    def test_total_return_is_positive_for_upward_trend(self):
        rets = pd.Series(np.full(252, 0.001))
        result = compute_benchmark_returns_metrics(rets)
        assert result["total_return"] > 0

    def test_total_return_is_negative_for_downward_trend(self):
        rets = pd.Series(np.full(252, -0.001))
        result = compute_benchmark_returns_metrics(rets)
        assert result["total_return"] < 0


class TestComputeBenchmarkComparison:
    def test_identical_returns_give_beta_near_one_alpha_near_zero(self):
        rets = _make_returns(1.0, 252, seed=1)
        result = compute_benchmark_comparison(rets, rets)
        assert result["beta"] == pytest.approx(1.0, abs=0.05)
        assert result["alpha"] == pytest.approx(0.0, abs=0.02)
        assert result["market_correlation"] == pytest.approx(1.0, abs=0.01)

    def test_higher_strategy_returns_give_positive_alpha(self):
        rng = np.random.default_rng(42)
        bench_rets = pd.Series(rng.normal(0.0005, 0.01, 252))
        strat_rets = bench_rets + pd.Series(rng.normal(0.0005, 0.005, 252))
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["alpha"] > 0

    def test_lower_strategy_returns_give_negative_alpha(self):
        rng = np.random.default_rng(42)
        bench_rets = pd.Series(rng.normal(0.001, 0.01, 252))
        strat_rets = bench_rets + pd.Series(rng.normal(-0.0005, 0.005, 252))
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["alpha"] < 0

    def test_up_capture_above_one_when_strategy_outperforms_in_up_markets(self):
        rng = np.random.default_rng(42)
        bench_rets = pd.Series(rng.normal(0.001, 0.01, 252))
        strat_rets = bench_rets * 1.5
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["up_capture"] > 1.0

    def test_down_capture_below_one_when_strategy_declines_less(self):
        rng = np.random.default_rng(42)
        bench_rets = pd.Series(rng.normal(0.001, 0.01, 252))
        strat_rets = bench_rets * 0.5
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["down_capture"] < 1.0

    def test_information_ratio_positive_with_alpha(self):
        rng = np.random.default_rng(42)
        bench_rets = pd.Series(rng.normal(0.0005, 0.01, 252))
        strat_rets = bench_rets + pd.Series(rng.normal(0.0005, 0.005, 252))
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["information_ratio"] > 0

    def test_returns_empty_dict_for_less_than_20_points(self):
        rets = pd.Series(np.random.normal(0, 0.01, 10))
        result = compute_benchmark_comparison(rets, rets)
        assert result == {}

    def test_tracking_error_is_positive(self):
        rng = np.random.default_rng(42)
        bench_rets = pd.Series(rng.normal(0.001, 0.01, 252))
        strat_rets = bench_rets + pd.Series(rng.normal(0, 0.005, 252))
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["tracking_error"] > 0

    def test_excess_cagr_matches_return_difference(self):
        strat_rets = pd.Series(np.full(252, 0.001))
        bench_rets = pd.Series(np.full(252, 0.0005))
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["excess_cagr"] > 0
        assert result["alpha"] > 0

    def test_relative_max_drawdown_is_negative_or_zero(self):
        strat_rets = _make_returns(1.0, 252, seed=1)
        bench_rets = _make_returns(0.8, 252, seed=2)
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result["relative_max_drawdown"] <= 0

    def test_beta_is_zero_when_benchmark_has_zero_variance(self):
        strat_rets = pd.Series(np.random.normal(0.001, 0.01, 252))
        bench_rets = pd.Series(np.full(252, 0.001))
        result = compute_benchmark_comparison(strat_rets, bench_rets)
        assert result.get("beta", -1) == 0.0


class TestBenchmarkConfig:
    def test_default_benchmark_symbol_is_spy(self):
        from vinu_research.config import DEFAULT_BENCHMARK_SYMBOL
        assert DEFAULT_BENCHMARK_SYMBOL == "SPY"

    def test_default_stock_price_url(self):
        from vinu_research.config import DEFAULT_STOCK_PRICE_API_URL
        assert DEFAULT_STOCK_PRICE_API_URL == "http://127.0.0.1:8081"

    def test_config_has_benchmark_symbol(self):
        from vinu_research.config import ResearchConfig
        cfg = ResearchConfig()
        assert hasattr(cfg, "benchmark_symbol")
        assert cfg.benchmark_symbol == "SPY"

    def test_config_has_stock_price_api_url(self):
        from vinu_research.config import ResearchConfig
        cfg = ResearchConfig()
        assert hasattr(cfg, "stock_price_api_url")


class TestBenchmarkReport:
    def test_report_contains_benchmark_section_when_metrics_present(self):
        from vinu_research.models import BacktestMetrics, BacktestResult
        from vinu_research.report import generate_report

        m = BacktestMetrics(cagr=0.12, sharpe_ratio=1.2, max_drawdown=-0.08, win_rate=0.55, annual_volatility=0.15)
        result = BacktestResult(
            run_id="r", strategy_name="S", metrics=m,
            benchmark_metrics={"SPY": {"sharpe_ratio": 1.0, "cagr": 0.08, "max_drawdown": -0.12,
                                       "annual_volatility": 0.18, "win_rate": 0.52,
                                       "alpha": 0.03, "beta": 0.8, "information_ratio": 0.7,
                                       "up_capture": 0.85, "down_capture": 0.60}},
            trade_count=50, equity_points=252,
        )
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test strategy", [], result, 1)
        assert "Benchmark Comparison (vs SPY)" in report
        assert "Alpha (ann.)" in report
        assert "Beta" in report
        assert "Market Capture" in report
        assert "Up Capture" in report
        assert "Down Capture" in report

    def test_report_shows_simple_comparison_without_alpha_beta(self):
        from vinu_research.models import BacktestMetrics, BacktestResult
        from vinu_research.report import generate_report

        m = BacktestMetrics(cagr=0.12, sharpe_ratio=1.2, max_drawdown=-0.08, win_rate=0.55, annual_volatility=0.15)
        result = BacktestResult(
            run_id="r", strategy_name="S", metrics=m,
            benchmark_metrics={"SPY": {"sharpe_ratio": 1.0, "cagr": 0.08, "max_drawdown": -0.12,
                                       "annual_volatility": 0.18, "win_rate": 0.52}},
            trade_count=50, equity_points=252,
        )
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test strategy", [], result, 1)
        assert "Benchmark Comparison (vs SPY)" in report
        assert "Alpha (ann.)" not in report
        assert "Market Capture" not in report

    def test_report_skips_benchmark_when_no_metrics(self):
        from vinu_research.models import BacktestMetrics, BacktestResult
        from vinu_research.report import generate_report

        m = BacktestMetrics(cagr=0.12, sharpe_ratio=1.2, max_drawdown=-0.08, win_rate=0.55, annual_volatility=0.15)
        result = BacktestResult(
            run_id="r", strategy_name="S", metrics=m,
            benchmark_metrics={},
            trade_count=50, equity_points=252,
        )
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test strategy", [], result, 1)
        assert "Benchmark Comparison" not in report


def _make_result(metrics_kw: dict | None = None) -> BacktestResult:
    m = BacktestMetrics(
        total_return=0.15,
        cagr=0.12,
        annual_volatility=0.15,
        sharpe_ratio=1.2,
        max_drawdown=-0.08,
        win_rate=0.55,
    )
    if metrics_kw:
        for k, v in metrics_kw.items():
            setattr(m, k, v)
    return BacktestResult(
        run_id="test-run",
        strategy_name="TestStrategy",
        metrics=m,
        benchmark_metrics={},
        trade_count=50,
        equity_points=252,
    )


class TestBenchmarkRiskCriticRules:
    def test_negative_alpha_triggers_suggestion(self):
        result = _make_result()
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(alpha=-0.05)
        suggestions = _check_benchmark_rules(result)
        suggestions_text = " ".join(suggestions)
        assert "alpha" in suggestions_text.lower()
        assert "destroying value" in suggestions_text

    def test_low_information_ratio_triggers_suggestion(self):
        result = _make_result()
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(information_ratio=0.3, alpha=0.02)
        suggestions = _check_benchmark_rules(result)
        suggestions_text = " ".join(suggestions)
        assert "information ratio" in suggestions_text.lower()

    def test_high_down_capture_triggers_suggestion(self):
        result = _make_result()
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(down_capture=1.5)
        suggestions = _check_benchmark_rules(result)
        suggestions_text = " ".join(suggestions)
        assert "down capture" in suggestions_text.lower()

    def test_negative_excess_cagr_triggers_suggestion(self):
        result = _make_result()
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(excess_cagr=-0.03, cagr=0.15)
        suggestions = _check_benchmark_rules(result)
        suggestions_text = " ".join(suggestions)
        assert "cagr below" in suggestions_text.lower()

    def test_benchmark_cagr_exceeds_strategy_triggers_suggestion_when_no_alpha(self):
        result = _make_result({"cagr": 0.05})
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(cagr=0.12, sharpe=1.5)
        suggestions = _check_benchmark_rules(result)
        suggestions_text = " ".join(suggestions)
        assert "SPY" in suggestions_text
        assert "exceeds" in suggestions_text

    def test_benchmark_metrics_empty_does_not_crash(self):
        result = _make_result()
        result.benchmark_metrics = {}
        suggestions = _check_benchmark_rules(result)
        assert isinstance(suggestions, list)

    def test_benchmark_rules_dont_fire_when_metrics_empty_dict(self):
        result = _make_result()
        result.benchmark_metrics = {"SPY": {}}
        suggestions = _check_benchmark_rules(result)
        benchmark_suggestions = [s for s in suggestions if "alpha" in s.lower() or "cagr" in s.lower() or "down capture" in s.lower()]
        assert len(benchmark_suggestions) == 0


class TestBenchmarkRulesInteractions:
    def test_multiple_benchmark_rules_can_fire_simultaneously(self):
        result = _make_result({"cagr": 0.03})
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(
            alpha=-0.03, information_ratio=0.3, down_capture=1.4,
            excess_cagr=-0.02, cagr=0.10,
        )
        suggestions = _check_benchmark_rules(result)
        assert len(suggestions) >= 4

    def test_negative_alpha_with_good_strategy_metrics_is_still_caught(self):
        result = _make_result({"sharpe_ratio": 2.0, "max_drawdown": -0.05})
        result.benchmark_metrics["SPY"] = _make_benchmark_metrics(alpha=-0.03)
        suggestions = _check_benchmark_rules(result)
        assert any("alpha" in s.lower() for s in suggestions)


class TestGeometricCagrCorrectness:
    """
    CAGR must compound the actual return sequence, not the arithmetic mean of daily
    returns — compounding the mean ignores volatility drag and overstates CAGR for
    any series with real variance. This directly regresses the bug where
    compute_benchmark_comparison used (1 + mean_daily) ** 252 - 1 while
    compute_benchmark_returns_metrics used proper geometric compounding, producing
    two different CAGR numbers for the same series in the same report.
    """

    def test_volatile_series_geometric_below_arithmetic_mean_compounded(self):
        # Alternating +20%/-20% has mean daily return 0%, but the actual compounded
        # value strictly decreases each cycle (volatility drag) — geometric CAGR
        # must be negative even though the naive "(1+mean)**252-1" formula gives 0%.
        n = 252
        rets = pd.Series([0.20 if i % 2 == 0 else -1 / 6 for i in range(n)])
        # 1.20 * (5/6) = 1.0 exactly per pair -> flat compounded value, but the
        # arithmetic-mean-compounded formula sees mean != 0 and reports growth.
        arithmetic_mean_compounded = (1 + rets.mean()) ** 252 - 1
        geometric = _geometric_cagr(rets)
        assert geometric == pytest.approx(0.0, abs=1e-6)
        assert arithmetic_mean_compounded > 0.01  # naive formula wrongly shows growth

    def test_benchmark_comparison_and_returns_metrics_agree_on_cagr(self):
        np.random.seed(7)
        n = 300
        strat = pd.Series(np.random.normal(0.001, 0.03, n))  # high daily vol
        bench = pd.Series(np.random.normal(0.0005, 0.01, n))

        returns_metrics_cagr = compute_benchmark_returns_metrics(strat)["cagr"]
        direct_cagr = _geometric_cagr(strat)
        assert returns_metrics_cagr == pytest.approx(direct_cagr, rel=1e-9)

        comparison = compute_benchmark_comparison(strat, bench)
        implied_strat_cagr = comparison["excess_cagr"] + _geometric_cagr(bench)
        assert implied_strat_cagr == pytest.approx(direct_cagr, rel=1e-9)
