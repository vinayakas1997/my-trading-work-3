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
