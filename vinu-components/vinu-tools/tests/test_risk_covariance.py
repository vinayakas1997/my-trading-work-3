import numpy as np
from vinu_tools.compute.risk.covariance import (
    dynamic_covariance,
    portfolio_variance,
    correlation_from_covariance,
)


def test_dynamic_covariance_basic():
    np.random.seed(42)
    prices = np.cumprod(1 + np.random.randn(3, 200) * 0.01, axis=1)
    cov = dynamic_covariance(prices, window=63)
    assert cov.shape == (3, 3)
    assert np.all(np.isfinite(cov))
    assert np.all(np.diag(cov) > 0)  # variances positive


def test_dynamic_covariance_single_asset():
    prices = np.cumprod(1 + np.random.randn(1, 100) * 0.01, axis=1)
    cov = dynamic_covariance(prices, window=63)
    assert cov.shape == (1, 1)
    assert cov[0, 0] > 0


def test_dynamic_covariance_symmetric():
    np.random.seed(42)
    prices = np.cumprod(1 + np.random.randn(5, 200) * 0.01, axis=1)
    cov = dynamic_covariance(prices, window=63)
    assert np.allclose(cov, cov.T)


def test_dynamic_covariance_shrinkage():
    np.random.seed(42)
    prices = np.cumprod(1 + np.random.randn(2, 30) * 0.01, axis=1)
    cov_raw = dynamic_covariance(prices, window=30, use_shrinkage=False)
    cov_shrunk = dynamic_covariance(prices, window=30, use_shrinkage=True)
    assert np.all(np.isfinite(cov_shrunk))


def test_dynamic_covariance_exponential():
    np.random.seed(42)
    prices = np.cumprod(1 + np.random.randn(3, 200) * 0.01, axis=1)
    cov = dynamic_covariance(prices, window=63, exponential_weight=True, decay_factor=0.97)
    assert cov.shape == (3, 3)
    assert np.all(np.isfinite(cov))


def test_portfolio_variance():
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    weights = np.array([0.5, 0.5])
    var = portfolio_variance(cov, weights)
    assert var > 0


def test_portfolio_variance_equal_weight():
    cov = np.array([[0.04, 0.01], [0.01, 0.09]])
    var = portfolio_variance(cov)
    assert var > 0


def test_correlation_from_covariance():
    cov = np.array([[0.04, 0.02], [0.02, 0.09]])
    corr = correlation_from_covariance(cov)
    assert np.allclose(corr[0, 0], 1.0)
    assert np.allclose(corr[1, 1], 1.0)
    expected_r = 0.02 / (0.2 * 0.3)
    assert abs(corr[0, 1] - expected_r) < 1e-10
