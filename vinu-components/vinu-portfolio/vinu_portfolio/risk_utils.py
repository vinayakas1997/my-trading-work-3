"""Stage A (A1, A2 — research-discussion-v1/complete-plan/02-stage-a-quick-wins.md):
hardens the correlation matrix vinu-portfolio computes from raw strategy
returns before OrderGuard's pairwise-correlation concentration check
(order_guard.py:_check_portfolio_concentration, via GET /portfolio/state)
-- and anything else downstream -- trusts it. A raw sample Pearson
correlation from a short/noisy return history (pandas .corr(), what both
PortfolioService.compute_correlation_matrix and build_portfolio computed
directly until this fix) is exactly the kind of thing that produces both
non-positive-semidefinite matrices (pairwise-NaN handling can do this) and
noisy off-diagonal entries that swing a pass/fail decision on limited
data. PyPortfolioOpt (audited this session, see
other-repos-world/comprison-other-vinu/11-pyportfolioopt.md) is the
reference for both fixes below; reimplemented here rather than taken as a
dependency, using scikit-learn's LedoitWolf (a real, well-tested estimator,
not a hand-rolled shrinkage formula) plus a small numpy-only spectral
repair.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

LOG = logging.getLogger(__name__)

# Eigenvalues within this of zero are treated as "already PSD, float noise
# only" -- don't perturb a matrix that doesn't need repair.
_PSD_TOLERANCE = 1e-8


def fix_nonpositive_semidefinite(corr: pd.DataFrame) -> pd.DataFrame:
    """Spectral repair (A1): eigen-decompose, clip negative eigenvalues to
    0, rebuild, renormalize back to a unit-diagonal correlation matrix.
    A no-op when the matrix is already PSD -- cheap enough to call
    unconditionally as a final safety net regardless of which upstream
    path produced `corr`."""
    if corr is None or corr.empty:
        return corr
    values = corr.to_numpy(dtype=float, copy=True)
    eigenvalues, eigenvectors = np.linalg.eigh(values)
    if np.all(eigenvalues >= -_PSD_TOLERANCE):
        return corr
    LOG.info(
        "Correlation matrix not positive-semidefinite (min eigenvalue %.6f) -- "
        "applying spectral repair", float(eigenvalues.min()),
    )
    eigenvalues = np.clip(eigenvalues, 0, None)
    fixed = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    diag = np.sqrt(np.clip(np.diag(fixed), 1e-12, None))
    fixed = fixed / np.outer(diag, diag)
    np.fill_diagonal(fixed, 1.0)
    return pd.DataFrame(fixed, index=corr.index, columns=corr.columns)


def _shrunk_correlation(returns_df: pd.DataFrame) -> pd.DataFrame | None:
    """Ledoit-Wolf shrinkage covariance (A2), converted to a correlation
    matrix -- less noisy than a raw sample correlation for a short/small
    return history, and shrinkage toward a well-conditioned target is PSD
    by construction. Returns None on any failure (fail-open, same posture
    as every other data-quality guard in this codebase) so the caller
    falls back to the raw .corr() it already had."""
    if returns_df is None or returns_df.shape[1] < 2:
        return None
    clean = returns_df.dropna()
    if clean.shape[0] < 2:
        return None
    try:
        from sklearn.covariance import LedoitWolf
        cov = LedoitWolf().fit(clean.to_numpy(dtype=float)).covariance_
        diag = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
        corr = cov / np.outer(diag, diag)
        np.fill_diagonal(corr, 1.0)
        return pd.DataFrame(corr, index=returns_df.columns, columns=returns_df.columns)
    except Exception as e:
        LOG.warning("Ledoit-Wolf shrinkage failed, falling back to raw correlation: %s", e)
        return None


def cap_concentration(weights: dict[str, float], cap: float, *, max_iter: int = 50) -> dict[str, float]:
    """Stage A (A4 — daily_stock_analysis's concentration-overlay pattern,
    see other-repos-world/comprison-other-vinu/04-daily_stock_analysis.md):
    enforce a per-name weight cap that actually *holds* after the weights
    sum to 1.

    The bug this fixes: `allocate_risk_parity` applied `min(w, cap)` and
    then renormalized, so renormalization pushed a capped weight straight
    back over the cap (3 strategies, one dominant -> capped at 0.30, others
    at 0.05 each -> total 0.40 -> renormalize -> 0.30/0.40 = 0.75). The
    composition-gap detector correctly flagged the result but nothing acted
    on it.

    Instead: clip every over-cap weight to the cap, redistribute the freed
    weight across the still-uncapped names in proportion to their current
    weight, and repeat until nothing exceeds the cap (or `max_iter`).

    The effective cap is raised to at least `1 / n` -- equal weight is the
    least concentrated a portfolio of n names can be, so a configured cap
    below that (the 0.30 default with only 2-3 strategies, say) is
    mathematically infeasible and is treated as a no-op rather than
    silently producing weights that don't sum to 1.
    """
    if not weights or cap >= 1.0:
        return dict(weights)
    w = {k: max(0.0, float(v)) for k, v in weights.items()}
    cap = max(cap, 1.0 / len(w))
    if not any(v > cap + 1e-12 for v in w.values()):
        return w

    for _ in range(max_iter):
        over = {k: v for k, v in w.items() if v > cap + 1e-12}
        if not over:
            break
        freed = sum(v - cap for v in over.values())
        for k in over:
            w[k] = cap
        under = {k: v for k, v in w.items() if v < cap - 1e-12}
        under_total = sum(under.values())
        if under_total <= 0:
            # Nothing left to absorb the freed weight -- the cap is
            # infeasible for this many names. Leave everyone at `cap`.
            break
        for k in under:
            w[k] += freed * (under[k] / under_total)
    return w


def robust_correlation_matrix(returns_df: pd.DataFrame | None) -> pd.DataFrame | None:
    """The one place vinu-portfolio should compute a correlation matrix
    from returns -- combines A2 (shrinkage, preferred) with A1 (spectral
    PSD repair as a final safety net regardless of which path produced the
    matrix). Returns None when there isn't enough data for even a raw
    correlation (mirrors returns_df.corr()'s own behavior on <2 columns)."""
    if returns_df is None or returns_df.shape[1] < 2:
        return None
    shrunk = _shrunk_correlation(returns_df)
    corr = shrunk if shrunk is not None else returns_df.corr()
    return fix_nonpositive_semidefinite(corr)
