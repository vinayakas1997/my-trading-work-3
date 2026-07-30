from __future__ import annotations

import numpy as np
import pandas as pd


def _garch_conditional_variance(
    returns: np.ndarray,
) -> np.ndarray:
    from vinu_tools.compute.risk.volatility import _garch_ml_estimate

    clean = returns[~np.isnan(returns)]
    if len(clean) < 10:
        return np.full_like(returns, np.nan, dtype=float)

    omega, alpha, beta = _garch_ml_estimate(clean)
    sigma2 = np.full_like(returns, np.nan, dtype=float)
    var = float(np.var(clean, ddof=1))
    for t in range(len(returns)):
        if np.isnan(returns[t]):
            continue
        if t == 0:
            var = omega + alpha * returns[t] ** 2 + beta * var
        else:
            var = omega + alpha * returns[t - 1] ** 2 + beta * var
        sigma2[t] = max(var, 1e-12)
    return sigma2


def dcc_shock_correlation(
    returns_df: pd.DataFrame,
    alpha: float = 0.03,
    beta: float = 0.95,
    min_periods: int = 20,
) -> dict:
    n = len(returns_df.columns)
    if n < 2:
        return {
            "calm_correlation": None,
            "crisis_correlation": None,
            "shock_delta": None,
            "shock_count": 0,
            "n_assets": n,
            "status": "insufficient_assets",
        }

    T = len(returns_df)
    standardized = np.full((T, n), np.nan)
    garch_failures = 0

    for i, col in enumerate(returns_df.columns):
        vals = returns_df[col].values
        cond_var = _garch_conditional_variance(vals)
        if np.all(np.isnan(cond_var)):
            cond_var = np.full_like(vals, np.nanvar(vals) if np.nanvar(vals) > 1e-12 else 1e-6)
            garch_failures += 1
        standardized[:, i] = vals / np.sqrt(cond_var)

    valid_rows = ~np.isnan(standardized).any(axis=1)
    z = standardized[valid_rows]
    T_z = len(z)

    if T_z < min_periods:
        return {
            "calm_correlation": None,
            "crisis_correlation": None,
            "shock_delta": None,
            "shock_count": 0,
            "n_assets": n,
            "status": "insufficient_data",
        }

    calm_corr = returns_df.loc[valid_rows].corr().values

    Q_bar = np.cov(z.T)
    Q_t = Q_bar.copy()
    for t in range(1, T_z):
        z_t_minus_1 = z[t - 1 : t]
        zz = z_t_minus_1.T @ z_t_minus_1
        Q_t = (1 - alpha - beta) * Q_bar + alpha * zz + beta * Q_t

    D_inv = np.diag(1.0 / np.sqrt(np.maximum(np.diag(Q_t), 1e-12)))
    crisis_corr = D_inv @ Q_t @ D_inv
    crisis_corr = np.clip(crisis_corr, -1.0, 1.0)
    np.fill_diagonal(crisis_corr, 1.0)

    delta = abs(crisis_corr - calm_corr).mean()
    shock_count = int(np.sum(abs(crisis_corr - calm_corr) > 0.4)) // 2
    n_high_pairs = int(np.sum(abs(crisis_corr) > 0.7)) // 2

    return {
        "calm_correlation": calm_corr.tolist(),
        "crisis_correlation": crisis_corr.tolist(),
        "strategies": list(returns_df.columns),
        "shock_delta": round(float(delta), 4),
        "shock_count": shock_count,
        "n_high_correlation_pairs": n_high_pairs,
        "n_assets": n,
        "garch_failures": garch_failures,
        "status": "ok",
    }
