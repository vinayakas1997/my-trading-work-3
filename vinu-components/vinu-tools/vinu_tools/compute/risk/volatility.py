from __future__ import annotations

import numpy as np
from typing import Literal

_ANNUALIZATION_FACTORS: dict[str, float] = {
    "1min": 252 * 390,
    "5min": 252 * 78,
    "15min": 252 * 26,
    "30min": 252 * 13,
    "1h": 252 * 6.5,
    "1D": 252,
    "1W": 52,
    "1M": 12,
}


def annualization_factor(time_format: str) -> float:
    return _ANNUALIZATION_FACTORS.get(time_format, 252)


def realized_volatility(
    returns: np.ndarray,
    window: int = 21,
    time_format: str = "1D",
    min_periods: int | None = None,
) -> np.ndarray:
    if min_periods is None:
        min_periods = window
    af = annualization_factor(time_format)
    result = np.full_like(returns, np.nan, dtype=float)
    for i in range(len(returns)):
        if i + 1 < min_periods:
            continue
        start = max(0, i + 1 - window)
        chunk = returns[start : i + 1]
        valid = chunk[~np.isnan(chunk)]
        if len(valid) < min_periods:
            continue
        result[i] = np.std(valid, ddof=1) * np.sqrt(af)
    return result


def ewma_volatility(
    returns: np.ndarray,
    lambda_: float = 0.94,
    time_format: str = "1D",
) -> np.ndarray:
    af = annualization_factor(time_format)
    result = np.full_like(returns, np.nan, dtype=float)
    variance = 0.0
    has_prior = False
    for i in range(len(returns)):
        if np.isnan(returns[i]):
            continue
        if not has_prior:
            variance = returns[i] ** 2
            has_prior = True
        else:
            variance = lambda_ * variance + (1 - lambda_) * returns[i] ** 2
        result[i] = np.sqrt(variance * af)
    return result


def _garch_neg_log_likelihood(
    params: np.ndarray, squared: np.ndarray, sigma2_init: float
) -> float:
    # omega is optimized in log-space (see _garch_ml_estimate) -- exp it
    # back out here so the recursion itself stays in real units.
    log_omega, alpha, beta = params
    omega = np.exp(log_omega)
    n = len(squared)
    sigma2 = np.empty(n)
    sigma2[0] = sigma2_init
    for t in range(1, n):
        sigma2[t] = omega + alpha * squared[t - 1] + beta * sigma2[t - 1]
    sigma2 = np.maximum(sigma2, 1e-12)
    return 0.5 * np.sum(np.log(sigma2) + squared / sigma2)


def _garch_ml_estimate(
    returns: np.ndarray,
    omega: float | None = None,
    alpha: float = 0.05,
    beta: float = 0.90,
    max_iter: int = 500,
    tol: float = 1e-10,
) -> tuple[float, float, float]:
    from scipy.optimize import minimize

    n = len(returns)
    squared = returns ** 2
    sample_var = float(np.var(returns, ddof=1)) if n > 1 else 1e-6
    sample_var = max(sample_var, 1e-12)

    if omega is None:
        # variance-targeting starting point: unconditional variance
        # omega / (1 - alpha - beta) == sample_var
        omega = max(sample_var * (1.0 - alpha - beta), 1e-10)

    # omega (~1e-5 for real return series) and alpha/beta (~0.05-0.9) sit
    # 4-5 orders of magnitude apart. Optimizing raw omega alongside them
    # breaks SLSQP's internal step-size/convergence logic -- it reports
    # "success" after a handful of evaluations while sitting exactly at
    # the starting guess with a large unexploited gradient (confirmed by
    # comparing NLL before/after adding this log-reparametrization: the
    # log-space version finds a real, better optimum every time). Optimizing
    # log(omega) instead puts all three parameters on a comparable scale.
    x0 = np.array([np.log(omega), alpha, beta])
    bounds = [
        (np.log(1e-12), np.log(sample_var * 10.0)),
        (1e-6, 0.999),
        (1e-6, 0.999),
    ]
    constraints = [{"type": "ineq", "fun": lambda x: 0.999 - x[1] - x[2]}]

    result = minimize(
        _garch_neg_log_likelihood,
        x0,
        args=(squared, sample_var),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": max_iter, "ftol": tol},
    )

    log_omega, alpha, beta = result.x
    return float(np.exp(log_omega)), float(alpha), float(beta)


def garch_volatility(
    returns: np.ndarray,
    time_format: str = "1D",
    omega: float | None = None,
    alpha: float | None = None,
    beta: float | None = None,
    fit: bool = True,
) -> tuple[np.ndarray, float, float, float]:
    af = annualization_factor(time_format)
    clean = returns[~np.isnan(returns)]
    if len(clean) < 10:
        result = np.full_like(returns, np.nan, dtype=float)
        return result, 0.0, 0.0, 0.0

    if fit or omega is None:
        omega, alpha, beta = _garch_ml_estimate(clean)
    else:
        omega = omega or 1e-6
        alpha = alpha or 0.1
        beta = beta or 0.85

    result = np.full_like(returns, np.nan, dtype=float)
    variance = np.var(clean, ddof=1) if len(clean) > 0 else 1e-6
    for i in range(len(returns)):
        if np.isnan(returns[i]):
            continue
        if i == 0:
            variance = omega + alpha * returns[i] ** 2 + beta * variance
        else:
            variance = omega + alpha * returns[i - 1] ** 2 + beta * variance
        result[i] = np.sqrt(np.maximum(variance * af, 1e-12))
    return result, alpha, beta, omega


def egarch_volatility(
    returns: np.ndarray,
    time_format: str = "1D",
    omega: float = -0.1,
    alpha: float = 0.1,
    beta: float = 0.85,
    gamma: float = 0.05,
) -> np.ndarray:
    af = annualization_factor(time_format)
    result = np.full_like(returns, np.nan, dtype=float)
    log_variance = np.log(np.var(returns[~np.isnan(returns)], ddof=1) + 1e-12)
    for i in range(len(returns)):
        if np.isnan(returns[i]):
            continue
        if i == 0:
            z = returns[i] / np.sqrt(np.exp(log_variance) + 1e-12)
        else:
            z = returns[i - 1] / np.sqrt(np.exp(log_variance) + 1e-12)
        abs_z = abs(z)
        log_variance = (
            omega
            + alpha * (abs_z - np.sqrt(2.0 / np.pi))
            + gamma * z
            + beta * log_variance
        )
        result[i] = np.sqrt(np.exp(log_variance) * af)
    return result
