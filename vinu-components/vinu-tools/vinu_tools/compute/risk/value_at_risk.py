from __future__ import annotations

import numpy as np
from scipy import stats as _stats


def historical_var(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    window: int | None = None,
) -> float:
    clean = returns[~np.isnan(returns)]
    if len(clean) < 5:
        return 0.0
    if window is not None and window < len(clean):
        clean = clean[-window:]
    return float(np.percentile(clean, (1 - confidence_level) * 100))


def historical_cvar(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    window: int | None = None,
) -> float:
    var = historical_var(returns, confidence_level, window)
    clean = returns[~np.isnan(returns)]
    if window is not None and window < len(clean):
        clean = clean[-window:]
    tail = clean[clean <= var]
    if len(tail) == 0:
        return var
    return float(np.mean(tail))


def parametric_var(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    window: int | None = None,
) -> float:
    clean = returns[~np.isnan(returns)]
    if len(clean) < 5:
        return 0.0
    if window is not None and window < len(clean):
        clean = clean[-window:]
    mu = np.mean(clean)
    sigma = np.std(clean, ddof=1)
    z = _stats.norm.ppf(1 - confidence_level)
    return float(mu + z * sigma)


def parametric_cvar(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    window: int | None = None,
) -> float:
    clean = returns[~np.isnan(returns)]
    if len(clean) < 5:
        return 0.0
    if window is not None and window < len(clean):
        clean = clean[-window:]
    mu = np.mean(clean)
    sigma = np.std(clean, ddof=1)
    z = _stats.norm.ppf(1 - confidence_level)
    pdf_z = _stats.norm.pdf(z)
    cdf_z = _stats.norm.cdf(z)
    if cdf_z <= 0:
        return float(mu + z * sigma)
    return float(mu - sigma * pdf_z / (1 - confidence_level))
