from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_research.portfolio import (
    analyze_portfolio,
    compute_beta_hedged_returns,
    compute_correlation_matrix,
    compute_rolling_beta,
)


def _make_returns(seed: int, n: int = 300, mean: float = 0.0003, std: float = 0.01) -> pd.Series:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.Series(rng.normal(mean, std, n), index=dates)


class TestCorrelationMatrix:
    def test_identical_series_have_correlation_one(self):
        r = _make_returns(1)
        corr = compute_correlation_matrix({"A": r, "B": r.copy()})
        assert corr.loc["A", "B"] == pytest.approx(1.0, abs=1e-9)

    def test_independent_series_have_low_correlation(self):
        a = _make_returns(1)
        b = _make_returns(2)
        corr = compute_correlation_matrix({"A": a, "B": b})
        assert abs(corr.loc["A", "B"]) < 0.3

    def test_inverse_series_have_correlation_near_negative_one(self):
        a = _make_returns(1)
        corr = compute_correlation_matrix({"A": a, "B": -a})
        assert corr.loc["A", "B"] == pytest.approx(-1.0, abs=1e-9)


class TestRollingBeta:
    def test_beta_of_series_to_itself_is_one(self):
        bench = _make_returns(3, std=0.015)
        beta = compute_rolling_beta(bench.copy(), bench, lookback_days=30)
        # Ignore the warm-up window where the rolling estimate hasn't stabilized.
        assert beta.iloc[60:].mean() == pytest.approx(1.0, abs=0.05)

    def test_beta_is_causal_not_lookahead(self):
        # Beta on day t must be computable from data available through day t-1 —
        # changing day t's own return must not change beta[t].
        bench = _make_returns(4, std=0.01)
        port = 1.2 * bench + _make_returns(5, std=0.005)

        beta_a = compute_rolling_beta(port.copy(), bench.copy(), lookback_days=30)

        port_mutated = port.copy()
        port_mutated.iloc[100] = 999.0  # blow up a single day's return
        beta_b = compute_rolling_beta(port_mutated, bench.copy(), lookback_days=30)

        # beta at day 100 itself must be unaffected by day 100's own (mutated) return.
        assert beta_a.iloc[100] == pytest.approx(beta_b.iloc[100], abs=1e-9)
        # But beta at day 101+ (which now has day 100 in its trailing window) does change.
        assert beta_a.iloc[101] != pytest.approx(beta_b.iloc[101], abs=1e-9)

    def test_zero_variance_benchmark_does_not_crash(self):
        bench = pd.Series(np.zeros(50), index=pd.date_range("2023-01-02", periods=50, freq="B"))
        port = _make_returns(6, n=50)
        beta = compute_rolling_beta(port, bench, lookback_days=10)
        assert np.isfinite(beta).all()


class TestBetaHedgedReturns:
    def test_perfectly_correlated_portfolio_hedges_to_near_zero_vol(self):
        # A portfolio that IS the benchmark (beta=1) should have its volatility
        # almost entirely removed by a beta-1 hedge, once the rolling estimate
        # has stabilized.
        bench = _make_returns(7, std=0.02)
        hedged, beta = compute_beta_hedged_returns(bench.copy(), bench, lookback_days=30, max_hedge_ratio=2.0)
        raw_vol_tail = bench.iloc[-100:].std()
        hedged_vol_tail = hedged.iloc[-100:].std()
        assert hedged_vol_tail < raw_vol_tail * 0.3

    def test_hedge_ratio_is_clipped_to_max(self):
        bench = _make_returns(8, std=0.005)
        port = 5.0 * bench  # extreme beta ~5
        _, beta = compute_beta_hedged_returns(port, bench, lookback_days=30, max_hedge_ratio=1.5)
        assert beta.abs().max() <= 1.5 + 1e-9

    def test_uncorrelated_portfolio_is_barely_changed_by_hedge(self):
        bench = _make_returns(9, std=0.01)
        independent_port = _make_returns(10, std=0.01)
        hedged, _ = compute_beta_hedged_returns(independent_port, bench, lookback_days=30)
        raw_tail = independent_port.reindex(hedged.index).iloc[-100:]
        hedged_tail = hedged.iloc[-100:]
        # Hedging near-zero beta shouldn't meaningfully change the return series.
        assert (hedged_tail - raw_tail).abs().mean() < raw_tail.std() * 0.5


class TestAnalyzePortfolio:
    def test_returns_none_for_single_symbol(self):
        r = _make_returns(11)
        result = analyze_portfolio({"A": r}, r, r, lookback_days=30)
        assert result is None

    def test_returns_none_when_history_too_short(self):
        r = _make_returns(12, n=10)
        result = analyze_portfolio({"A": r, "B": r * 0.9}, r, r, lookback_days=60)
        assert result is None

    def test_full_analysis_on_sufficient_data(self):
        bench = _make_returns(13, n=400, std=0.012)
        a = 1.1 * bench + _make_returns(14, n=400, std=0.004)
        b = 0.8 * bench + _make_returns(15, n=400, std=0.004)
        portfolio_returns = (a + b) / 2

        result = analyze_portfolio(
            {"A": a, "B": b}, portfolio_returns, bench, lookback_days=60,
        )

        assert result is not None
        assert set(result.symbols) == {"A", "B"}
        assert "A" in result.correlation_matrix
        assert -1.0 <= result.avg_pairwise_correlation <= 1.0
        assert result.n_observations > 0
        assert np.isfinite(result.raw_sharpe)
        assert np.isfinite(result.hedged_sharpe)
