from __future__ import annotations

import numpy as np
from scipy import stats as _stats


def _d1(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
) -> float:
    return (
        np.log(spot / strike)
        + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry
    ) / (volatility * np.sqrt(time_to_expiry))


def _d2(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
) -> float:
    return _d1(spot, strike, time_to_expiry, volatility, risk_free_rate) - volatility * np.sqrt(time_to_expiry)


def delta(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: str = "call",
) -> float:
    if time_to_expiry <= 0:
        return 0.0
    d1 = _d1(spot, strike, time_to_expiry, volatility, risk_free_rate)
    if option_type == "call":
        return float(_stats.norm.cdf(d1))
    return float(_stats.norm.cdf(d1) - 1)


def gamma(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
) -> float:
    if time_to_expiry <= 0 or spot <= 0:
        return 0.0
    d1 = _d1(spot, strike, time_to_expiry, volatility, risk_free_rate)
    return float(_stats.norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_expiry)))


def vega(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
) -> float:
    if time_to_expiry <= 0:
        return 0.0
    d1 = _d1(spot, strike, time_to_expiry, volatility, risk_free_rate)
    return float(spot * _stats.norm.pdf(d1) * np.sqrt(time_to_expiry))


def theta(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: str = "call",
) -> float:
    if time_to_expiry <= 0:
        return 0.0
    d1 = _d1(spot, strike, time_to_expiry, volatility, risk_free_rate)
    d2 = _d2(spot, strike, time_to_expiry, volatility, risk_free_rate)
    pdf_d1 = _stats.norm.pdf(d1)
    if option_type == "call":
        result = (
            -spot * pdf_d1 * volatility / (2 * np.sqrt(time_to_expiry))
            - risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * _stats.norm.cdf(d2)
        )
    else:
        result = (
            -spot * pdf_d1 * volatility / (2 * np.sqrt(time_to_expiry))
            + risk_free_rate * strike * np.exp(-risk_free_rate * time_to_expiry) * _stats.norm.cdf(-d2)
        )
    return float(result)


def rho(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: str = "call",
) -> float:
    if time_to_expiry <= 0:
        return 0.0
    d2 = _d2(spot, strike, time_to_expiry, volatility, risk_free_rate)
    if option_type == "call":
        return float(strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * _stats.norm.cdf(d2))
    return float(-strike * time_to_expiry * np.exp(-risk_free_rate * time_to_expiry) * _stats.norm.cdf(-d2))
