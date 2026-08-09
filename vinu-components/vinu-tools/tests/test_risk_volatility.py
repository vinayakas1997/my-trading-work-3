import numpy as np
from vinu_tools.compute.risk.volatility import (
    realized_volatility,
    ewma_volatility,
    garch_volatility,
    egarch_volatility,
    annualization_factor,
)


def test_annualization_factor():
    assert annualization_factor("1D") == 252
    assert annualization_factor("1W") == 52
    assert annualization_factor("1M") == 12
    assert annualization_factor("1h") == 252 * 6.5


def test_realized_volatility_constant_returns():
    returns = np.full(100, 0.01)
    vol = realized_volatility(returns, window=21)
    assert np.all(np.isnan(vol[:20]))  # not enough periods
    assert np.all(vol[20:] > 0)  # has values


def test_realized_volatility_zero_returns():
    returns = np.zeros(50)
    vol = realized_volatility(returns, window=10)
    assert np.all(vol[9:] == 0.0)


def test_realized_volatility_known_values():
    np.random.seed(42)
    returns = np.random.randn(100) * 0.02
    vol = realized_volatility(returns, window=63)
    last = vol[~np.isnan(vol)][-1]
    assert 0.1 < last < 0.6  # reasonable range for 2% daily noise annualized


def test_ewma_volatility_basic():
    returns = np.full(50, 0.01)
    vol = ewma_volatility(returns, lambda_=0.94)
    assert np.all(vol[1:] > 0)
    assert not np.any(np.isnan(vol[1:]))


def test_ewma_volatility_decay():
    returns = np.zeros(50)
    returns[0] = 0.1
    vol = ewma_volatility(returns, lambda_=0.8)
    assert np.isfinite(vol[0])
    assert vol[1] > 0
    assert vol[-1] < vol[1]  # decays


def test_garch_volatility_fit():
    np.random.seed(42)
    returns = np.random.randn(200) * 0.01
    cond_vol, alpha, beta, omega = garch_volatility(returns, fit=True)
    assert 0 < alpha < 1
    assert 0 < beta < 1
    assert omega > 0
    assert not np.all(np.isnan(cond_vol))


def test_garch_volatility_fixed_params():
    np.random.seed(42)
    returns = np.random.randn(100) * 0.01
    cond_vol, alpha, beta, omega = garch_volatility(
        returns, fit=False, omega=1e-6, alpha=0.1, beta=0.85
    )
    assert alpha == 0.1
    assert beta == 0.85
    assert not np.all(np.isnan(cond_vol))


def test_garch_volatility_omega_matches_variance_targeting_identity():
    # Regression test for a fixed bug: the old hand-rolled gradient-ascent
    # optimizer used an unscaled, incomplete gradient and produced omega
    # values ~1000x too large. The true MLE omega must roughly satisfy the
    # unconditional-variance identity: omega / (1 - alpha - beta) == sample_var.
    np.random.seed(7)
    returns = np.random.randn(300) * 0.015
    _, alpha, beta, omega = garch_volatility(returns, fit=True)
    sample_var = np.var(returns, ddof=1)
    implied_var = omega / (1 - alpha - beta)
    assert 0.2 * sample_var < implied_var < 5 * sample_var


def test_garch_volatility_short_input():
    returns = np.array([0.01, 0.02])
    cond_vol, _, _, _ = garch_volatility(returns)
    assert np.all(np.isnan(cond_vol))


def test_egarch_volatility_basic():
    np.random.seed(42)
    returns = np.random.randn(100) * 0.01
    vol = egarch_volatility(returns)
    assert not np.all(np.isnan(vol))
    assert np.all(vol[vol > 0])  # all positive


def test_egarch_volatility_asymmetry():
    np.random.seed(42)
    neg_returns = -np.abs(np.random.randn(100) * 0.01)
    pos_returns = np.abs(np.random.randn(100) * 0.01)
    neg_vol = egarch_volatility(neg_returns, gamma=-0.1)
    pos_vol = egarch_volatility(pos_returns, gamma=-0.1)
    neg_recent = neg_vol[~np.isnan(neg_vol)]
    pos_recent = pos_vol[~np.isnan(pos_vol)]
    if len(neg_recent) > 0 and len(pos_recent) > 0:
        assert neg_recent[-1] > pos_recent[-1] * 0.5  # asymmetry visible
