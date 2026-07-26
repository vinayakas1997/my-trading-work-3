import numpy as np
from vinu_tools.compute.risk.value_at_risk import (
    historical_var,
    historical_cvar,
    parametric_var,
    parametric_cvar,
)


def test_historical_var_basic():
    returns = np.random.randn(1000) * 0.02
    var = historical_var(returns, confidence_level=0.95)
    assert var < 0  # VaR is negative for normal returns
    assert var > -0.1  # reasonable bound


def test_historical_var_confidence_levels():
    returns = np.random.randn(1000) * 0.02
    var_95 = historical_var(returns, confidence_level=0.95)
    var_99 = historical_var(returns, confidence_level=0.99)
    assert var_99 <= var_95  # 99% VaR is more negative


def test_historical_var_short_input():
    returns = np.array([0.01, 0.02])
    var = historical_var(returns)
    assert var == 0.0  # not enough data


def test_historical_cvar():
    returns = np.random.randn(1000) * 0.02
    var = historical_var(returns, confidence_level=0.95)
    cvar = historical_cvar(returns, confidence_level=0.95)
    assert cvar <= var  # CVaR is worse than VaR


def test_parametric_var_basic():
    returns = np.random.randn(1000) * 0.02
    var = parametric_var(returns, confidence_level=0.95)
    assert var < 0


def test_parametric_var_vs_historical():
    np.random.seed(42)
    returns = np.random.randn(1000) * 0.02
    hist = historical_var(returns, confidence_level=0.95)
    para = parametric_var(returns, confidence_level=0.95)
    assert abs(hist - para) < 0.01  # close for normal data


def test_parametric_cvar():
    returns = np.random.randn(1000) * 0.02
    var = parametric_var(returns, confidence_level=0.95)
    cvar = parametric_cvar(returns, confidence_level=0.95)
    assert cvar <= var
