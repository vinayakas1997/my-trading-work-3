import numpy as np
from vinu_tools.compute.risk.greeks import (
    delta,
    gamma,
    vega,
    theta,
    rho,
)


def test_call_delta_atm():
    d = delta(spot=100, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05, option_type="call")
    assert 0.4 < d < 0.6  # ATM call delta ~0.5


def test_put_delta_atm():
    d = delta(spot=100, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05, option_type="put")
    assert -0.6 < d < -0.4  # ATM put delta ~-0.5


def test_call_delta_itm():
    d = delta(spot=110, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05, option_type="call")
    assert d > 0.6  # ITM call


def test_call_delta_otm():
    d = delta(spot=90, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05, option_type="call")
    assert d < 0.4  # OTM call


def test_gamma_positive():
    g = gamma(spot=100, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05)
    assert g > 0


def test_vega_positive():
    v = vega(spot=100, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05)
    assert v > 0


def test_theta_call():
    t = theta(spot=100, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05, option_type="call")
    assert t < 0  # theta is negative for long options


def test_rho_call_positive():
    r = rho(spot=100, strike=100, time_to_expiry=30/365, volatility=0.20, risk_free_rate=0.05, option_type="call")
    assert r > 0
