from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.shock_correlation import _gerber_correlation, dcc_shock_correlation


def _returns_df(symbols: list[str], n_days: int = 252, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {}
    for i, sym in enumerate(symbols):
        noise = rng.normal(0.001, 0.015, n_days)
        if i > 0:
            noise += 0.3 * data[symbols[0]]
        data[sym] = noise
    idx = pd.date_range("2024-01-01", periods=n_days, freq="B")
    return pd.DataFrame(data, index=idx)


class TestDccShockCorrelation:
    def test_insufficient_assets_when_single_symbol(self) -> None:
        df = _returns_df(["AAPL"], n_days=100)
        result = dcc_shock_correlation(df)
        assert result["status"] == "insufficient_assets"
        assert result["n_assets"] == 1

    def test_insufficient_data_when_too_few_periods(self) -> None:
        df = _returns_df(["AAPL", "MSFT"], n_days=5)
        result = dcc_shock_correlation(df)
        assert result["status"] == "insufficient_data"

    def test_returns_ok_for_two_symbols(self) -> None:
        df = _returns_df(["AAPL", "MSFT"], n_days=252)
        result = dcc_shock_correlation(df)
        assert result["status"] == "ok"
        assert result["n_assets"] == 2
        assert result["strategies"] == ["AAPL", "MSFT"]

    def test_calm_and_crisis_correlation_matrices_have_same_shape(self) -> None:
        df = _returns_df(["AAPL", "MSFT", "GOOG"], n_days=252)
        result = dcc_shock_correlation(df)
        calm = np.array(result["calm_correlation"])
        crisis = np.array(result["crisis_correlation"])
        assert calm.shape == (3, 3)
        assert crisis.shape == (3, 3)
        assert np.allclose(np.diag(calm), 1.0)
        assert np.allclose(np.diag(crisis), 1.0)

    def test_shock_delta_is_positive_float(self) -> None:
        df = _returns_df(["AAPL", "MSFT", "GOOG"], n_days=252, seed=7)
        result = dcc_shock_correlation(df)
        assert isinstance(result["shock_delta"], float)
        assert result["shock_delta"] >= 0.0

    def test_shock_count_is_nonnegative_int(self) -> None:
        df = _returns_df(["AAPL", "MSFT", "GOOG"], n_days=252)
        result = dcc_shock_correlation(df)
        assert isinstance(result["shock_count"], int)
        assert result["shock_count"] >= 0

    def test_n_high_correlation_pairs_is_nonnegative_int(self) -> None:
        df = _returns_df(["AAPL", "MSFT", "GOOG"], n_days=252)
        result = dcc_shock_correlation(df)
        assert isinstance(result["n_high_correlation_pairs"], int)
        assert result["n_high_correlation_pairs"] >= 0

    def test_garch_failures_low_with_realistic_data(self) -> None:
        df = _returns_df(["AAPL", "MSFT"], n_days=252, seed=42)
        result = dcc_shock_correlation(df)
        assert result["garch_failures"] == 0

    def test_handles_nan_returns_gracefully(self) -> None:
        idx = pd.date_range("2024-01-01", periods=200, freq="B")
        data = {
            "AAPL": np.random.default_rng(1).normal(0.0, 0.02, 200),
            "MSFT": np.random.default_rng(2).normal(0.0, 0.02, 200),
        }
        df = pd.DataFrame(data, index=idx)
        df.iloc[50:60, 0] = np.nan
        df.iloc[100:110, 1] = np.nan
        result = dcc_shock_correlation(df)
        assert result["status"] == "ok"

    def test_highly_correlated_symbols_produce_high_crisis_correlation(self) -> None:
        rng = np.random.default_rng(42)
        common = rng.normal(0.001, 0.02, 300)
        data = {
            "A": common + rng.normal(0, 0.001, 300),
            "B": common + rng.normal(0, 0.001, 300),
        }
        df = pd.DataFrame(data, index=pd.date_range("2024-01-01", periods=300, freq="B"))
        result = dcc_shock_correlation(df)
        crisis = np.array(result["crisis_correlation"])
        assert crisis[0, 1] > 0.9


class TestGerberCorrelation:
    def test_diagonal_is_exactly_one(self) -> None:
        rng = np.random.default_rng(3)
        returns = rng.normal(0.0, 0.01, (200, 4))
        corr = _gerber_correlation(returns)
        assert np.allclose(np.diag(corr), 1.0)

    def test_symmetric_and_bounded(self) -> None:
        rng = np.random.default_rng(4)
        returns = rng.normal(0.0, 0.01, (200, 3))
        corr = _gerber_correlation(returns)
        assert np.allclose(corr, corr.T)
        assert np.all(corr <= 1.0 + 1e-9) and np.all(corr >= -1.0 - 1e-9)

    def test_highly_correlated_series_score_near_one(self) -> None:
        rng = np.random.default_rng(5)
        common = rng.normal(0.001, 0.02, 300)
        returns = np.column_stack(
            [common + rng.normal(0, 0.0005, 300), common + rng.normal(0, 0.0005, 300)]
        )
        corr = _gerber_correlation(returns)
        assert corr[0, 1] > 0.8

    def test_ignores_small_fluctuations_below_threshold(self) -> None:
        # Two series that only ever move together on large days, and
        # disagree on small/noisy days below the Gerber threshold — the
        # whole point of Gerber vs. raw correlation is that small noise
        # shouldn't dominate the co-movement read the way it can with a
        # raw Pearson correlation on noisy small moves.
        rng = np.random.default_rng(6)
        n = 400
        std = 0.01
        big_days = rng.random(n) < 0.1
        a = np.where(big_days, rng.choice([-1, 1], n) * std * 2, rng.normal(0, std * 0.1, n))
        b = np.where(big_days, a, rng.normal(0, std * 0.1, n) * -1)
        returns = np.column_stack([a, b])
        corr = _gerber_correlation(returns)
        assert corr[0, 1] > 0.5
