from __future__ import annotations

import numpy as np
from typing import Any


def _shrinkage_target_correlation(matrix: np.ndarray) -> float:
    n = matrix.shape[0]
    if n < 2:
        return 0.0
    variances = np.diag(matrix)
    valid = variances > 0
    if not np.any(valid):
        return 0.0
    std = np.where(valid, np.sqrt(variances), 1.0)
    corr = matrix / np.outer(std, std)
    np.fill_diagonal(corr, 0.0)
    total = np.sum(corr[valid, :][:, valid])
    count = np.sum(valid) ** 2 - np.sum(valid)
    if count <= 0:
        return 0.0
    return total / count


def _ledoit_wolf_shrinkage(
    sample_cov: np.ndarray,
    returns: np.ndarray,
) -> tuple[np.ndarray, float]:
    n, t = returns.shape
    if n < 2 or t < 2:
        return sample_cov, 0.0

    target_corr = _shrinkage_target_correlation(sample_cov)
    variances = np.diag(sample_cov)
    std = np.sqrt(np.maximum(variances, 1e-12))
    target_cov = np.outer(std, std) * target_corr
    np.fill_diagonal(target_cov, variances)

    returns_centered = returns - np.mean(returns, axis=1, keepdims=True)

    pi_sum = 0.0
    for i in range(n):
        for j in range(n):
            if i > j:
                continue
            returns_ij = returns_centered[i] * returns_centered[j]
            var_ij = np.var(returns_ij, ddof=1)
            theta_ij = var_ij / t
            pi_sum += theta_ij

    gamma = np.sum((sample_cov - target_cov) ** 2)
    shrinkage = max(0.0, min(1.0, pi_sum / max(gamma, 1e-12)))
    shrunk = shrinkage * target_cov + (1 - shrinkage) * sample_cov
    return shrunk, shrinkage


def dynamic_covariance(
    price_matrix: np.ndarray,
    window: int = 63,
    use_shrinkage: bool = True,
    exponential_weight: bool = False,
    decay_factor: float = 0.97,
    min_periods: int | None = None,
) -> np.ndarray:
    if min_periods is None:
        min_periods = max(window // 2, 10)

    n_assets, n_periods = price_matrix.shape
    log_returns = np.diff(np.log(np.maximum(price_matrix, 1e-12)), axis=1)

    if log_returns.shape[1] < min_periods:
        return np.full((n_assets, n_assets), np.nan)

    recent = log_returns[:, -window:] if window < log_returns.shape[1] else log_returns

    if exponential_weight:
        n = recent.shape[1]
        weights = np.array([decay_factor ** (n - 1 - i) for i in range(n)])
        weights = weights / np.sum(weights)
        mean = np.average(recent, axis=1, weights=weights)
        centered = recent - mean.reshape(-1, 1)
        sample_cov = np.dot(centered * weights, centered.T)
    else:
        sample_cov = np.atleast_2d(np.cov(recent))

    if use_shrinkage and n_assets > 1:
        shrunk, _ = _ledoit_wolf_shrinkage(sample_cov, recent)
        return shrunk

    return sample_cov


def portfolio_variance(
    covariance_matrix: np.ndarray,
    weights: np.ndarray | None = None,
) -> float:
    n = covariance_matrix.shape[0]
    if weights is None:
        weights = np.ones(n) / n
    return float(np.dot(weights.T, np.dot(covariance_matrix, weights)))


def correlation_from_covariance(covariance_matrix: np.ndarray) -> np.ndarray:
    variances = np.diag(covariance_matrix)
    std = np.sqrt(np.maximum(variances, 1e-12))
    corr = covariance_matrix / np.outer(std, std)
    corr = np.clip(corr, -1, 1)
    return corr
