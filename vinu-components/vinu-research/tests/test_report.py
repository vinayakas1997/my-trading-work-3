from __future__ import annotations

from vinu_research.models import BacktestMetrics, BacktestResult, CriticFeedback, IterationRecord
from vinu_research.report import generate_report, format_metrics_table


def _make_record(iteration: int, sharpe: float, max_dd: float, win_rate: float, verdict: str) -> IterationRecord:
    metrics = BacktestMetrics(sharpe_ratio=sharpe, max_drawdown=max_dd, win_rate=win_rate)
    result = BacktestResult(
        run_id=f"r{iteration}", strategy_name="s", metrics=metrics,
        benchmark_metrics={}, trade_count=10, equity_points=100,
    )
    critique = CriticFeedback(verdict=verdict, reasoning="test", suggestions=["improve X", "add Y"])
    return IterationRecord(iteration=iteration, strategy_code="code", result=result, critique=critique)


class TestGenerateReport:
    def test_empty_history(self):
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test", [], None, -1)
        assert "FINAL RESEARCH REPORT" in report
        assert "AAPL" in report

    def test_with_history(self):
        record = _make_record(1, 1.2, -0.1, 0.5, "REFINE")
        result = record.result
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test", [record], result, 1)
        assert "FINAL RESEARCH REPORT" in report
        assert "Sharpe" in report
        assert "MaxDD" in report

    def test_benchmarks_shown(self):
        record = _make_record(1, 1.2, -0.1, 0.5, "PASS")
        result = record.result
        result.benchmark_metrics = {"SPY": {"sharpe_ratio": 0.8, "total_return": 0.1}}
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test", [record], result, 1)
        assert "Benchmark" in report
        assert "SPY" in report

    def test_key_findings_deduped(self):
        r1 = _make_record(1, 0.5, -0.2, 0.3, "REFINE")
        r2 = _make_record(2, 0.6, -0.15, 0.4, "REFINE")
        report = generate_report("AAPL", "2024-01-01", "2024-12-31", "test", [r1, r2], r2.result, 2)
        assert "improve X" in report
        assert "add Y" in report


class TestFormatMetricsTable:
    def test_returns_formatted_string(self):
        metrics = {"total_return": 0.15, "sharpe_ratio": 1.2, "max_drawdown": -0.1}
        table = format_metrics_table(metrics)
        assert "Total Return" in table
        assert "Sharpe" in table
        assert "Max DD" in table
