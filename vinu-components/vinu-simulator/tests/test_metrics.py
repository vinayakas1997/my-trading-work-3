from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_simulator.engine.metrics import compute_performance_metrics


class TestMetrics:
    def test_compute_performance_metrics_basic(self):
        values = pd.Series([1.0, 1.1, 1.2, 1.15, 1.25, 1.3, 1.28, 1.35, 1.4, 1.5])
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        assert metrics["total_return"] == 0.5
        assert metrics["cagr"] > 0
        assert metrics["sharpe_ratio"] != 0.0
        assert metrics["max_drawdown"] < 0

    def test_compute_performance_metrics_flat(self):
        values = pd.Series([1.0] * 10)
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        assert metrics["total_return"] == 0.0
        assert metrics["cagr"] == 0.0
        assert metrics["sharpe_ratio"] == 0.0

    def test_compute_performance_metrics_all_positive(self):
        values = pd.Series([1.0, 1.05, 1.10, 1.15, 1.20, 1.25])
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        assert metrics["max_drawdown"] >= 0  # no drawdown
        assert metrics["win_rate"] == 1.0

    def test_compute_performance_metrics_all_negative(self):
        values = pd.Series([1.0, 0.95, 0.90, 0.85, 0.80, 0.75])
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        assert metrics["total_return"] < 0
        assert metrics["max_drawdown"] < 0
        assert metrics["win_rate"] == 0.0

    def test_compute_performance_metrics_empty(self):
        metrics = compute_performance_metrics(
            pd.Series(dtype=float),
            pd.Series(dtype=float),
        )
        assert metrics["total_return"] == 0.0

    def test_compute_performance_metrics_max_drawdown(self):
        values = pd.Series([1.0, 1.2, 1.5, 1.3, 1.4, 1.6, 1.2, 1.3])
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        expected_max_dd = (1.2 / 1.6) - 1
        assert abs(metrics["max_drawdown"] - expected_max_dd) < 1e-6


class TestUndefinedSortinoCalmar:
    """
    #39: zero losing days / zero drawdown is mathematically "undefined", not a
    genuine Sortino/Calmar of 0.0 — that reads identically to a mediocre
    strategy. A strictly-monotonic-up equity curve must report a large
    (sentinel) value distinguishable from the flat/no-gain case, which stays 0.0.
    """

    def test_no_losing_days_reports_sentinel_not_zero(self):
        # Strictly increasing every day -> no losing days at all.
        values = pd.Series([1.0, 1.05, 1.10, 1.15, 1.20, 1.25])
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        assert metrics["sortino_ratio"] > 100.0
        assert metrics["calmar_ratio"] > 100.0

    def test_flat_series_still_reports_zero_not_sentinel(self):
        # No losses AND no gain -- genuinely neutral, not "undefined-excellent".
        values = pd.Series([1.0] * 10)
        returns = values.pct_change().dropna()
        metrics = compute_performance_metrics(values, returns)
        assert metrics["sortino_ratio"] == 0.0
        assert metrics["calmar_ratio"] == 0.0

    def test_sentinel_survives_compute_full_metrics_finite_sanitization(self):
        from vinu_simulator.engine.metrics import compute_full_metrics

        values = pd.Series([1.0, 1.05, 1.10, 1.15, 1.20, 1.25])
        returns = values.pct_change().dropna()
        metrics = compute_full_metrics(values, returns, full=False)
        # compute_full_metrics's inf/-inf/nan -> 0.0 pass must not also zero out
        # the finite sentinel used to represent "undefined" here.
        assert metrics["sortino_ratio"] > 100.0
        assert metrics["calmar_ratio"] > 100.0
