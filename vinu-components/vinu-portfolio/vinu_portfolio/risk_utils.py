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


def hrp_weights(returns_df: "pd.DataFrame | None") -> dict[str, float] | None:
    """Stage C (C11): Hierarchical Risk Parity (López de Prado 2016).

    Correlation-aware allocation that -- unlike mean-variance or full
    risk-parity -- never inverts the covariance matrix, so an
    ill-conditioned correlation estimate (short history, tiny universe)
    degrades to a flatter dendrogram rather than a blow-up. Uses the same
    A1/A2-hardened `robust_correlation_matrix` for the distance metric.

    Returns a name -> weight dict summing to 1.0, or None if there isn't
    enough data to cluster (caller falls back to inverse-vol).
    """
    if returns_df is None or returns_df.shape[1] < 2:
        return None
    clean = returns_df.dropna(axis=1, how="all").dropna(axis=0, how="any")
    n = clean.shape[1]
    if n < 2 or clean.shape[0] < n + 5:
        return None
    try:
        from scipy.cluster.hierarchy import linkage, to_tree
        from scipy.spatial.distance import squareform

        cov = clean.cov()
        corr = robust_correlation_matrix(clean)
        if corr is None:
            return None
        corr = corr.reindex(index=clean.columns, columns=clean.columns)
        dist = np.sqrt(np.clip((1.0 - corr.to_numpy()) / 2.0, 0.0, 1.0))
        np.fill_diagonal(dist, 0.0)
        link = linkage(squareform(dist, checks=False), method="single")

        # quasi-diagonalisation: leaf order of the dendrogram
        order = _leaf_order(to_tree(link), n)
        cols = list(clean.columns)
        ordered = [cols[i] for i in order]

        w = _hrp_bisect(cov.to_numpy(), order)
        raw = {cols[i]: float(w[k]) for k, i in enumerate(order)}
        total = sum(raw.values())
        if total <= 0:
            return None
        return {name: raw.get(name, 0.0) / total for name in cols}
    except Exception as exc:  # noqa: BLE001 -- fail-open to inverse-vol
        LOG.warning("HRP allocation failed (%s), caller should fall back", exc)
        return None


def _leaf_order(node, n: int) -> list[int]:
    if node is None:
        return []
    if node.is_leaf():
        return [node.id]
    return _leaf_order(node.get_left(), n) + _leaf_order(node.get_right(), n)


def _hrp_bisect(cov: np.ndarray, order: list[int]) -> np.ndarray:
    """Recursive bisection over the quasi-diagonalised covariance."""
    w = np.ones(len(order))
    clusters = [list(range(len(order)))]
    while clusters:
        clusters = [
            c[j:k]
            for c in clusters
            for j, k in ((0, len(c) // 2), (len(c) // 2, len(c)))
            if len(c) > 1
        ]
        for i in range(0, len(clusters), 2):
            left, right = clusters[i], clusters[i + 1]
            l_var = _cluster_var(cov, [order[t] for t in left])
            r_var = _cluster_var(cov, [order[t] for t in right])
            alpha = 1.0 - l_var / (l_var + r_var) if (l_var + r_var) > 0 else 0.5
            for t in left:
                w[t] *= alpha
            for t in right:
                w[t] *= 1.0 - alpha
    return w


def _cluster_var(cov: np.ndarray, idx: list[int]) -> float:
    sub = cov[np.ix_(idx, idx)]
    ivp = 1.0 / np.clip(np.diag(sub), 1e-12, None)
    ivp /= ivp.sum()
    return float(ivp @ sub @ ivp)


def rescale_correlated_clusters(
    weights: dict[str, float],
    corr: "pd.DataFrame | None",
    *,
    corr_threshold: float = 0.8,
    max_cluster_weight: float = 1.0,
) -> dict[str, float]:
    """Stage C (C12): a post-construction rescaling pass over the *whole*
    target-weight set. The per-strategy cap (`cap_concentration`) and
    OrderGuard's per-order checks each only reason about one name at a
    time; a book of five names that all move together is a concentrated
    bet no single-name check catches. This groups names whose pairwise
    correlation is >= `corr_threshold` and, if a cluster's combined weight
    exceeds `max_cluster_weight`, scales that cluster down and redistributes
    the freed weight to names outside any over-weight cluster.

    `max_cluster_weight >= 1.0` (default) is a no-op. Fail-open: any error
    returns the weights unchanged.
    """
    if not weights or corr is None or max_cluster_weight >= 1.0:
        return dict(weights)
    try:
        names = [n for n in weights if n in corr.columns]
        if len(names) < 2:
            return dict(weights)

        # union-find over strongly-correlated pairs
        parent = {n: n for n in names}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i, a in enumerate(names):
            for b in names[i + 1:]:
                try:
                    if abs(float(corr.loc[a, b])) >= corr_threshold:
                        parent[find(a)] = find(b)
                except (KeyError, TypeError, ValueError):
                    continue

        clusters: dict[str, list[str]] = {}
        for n in names:
            clusters.setdefault(find(n), []).append(n)

        out = dict(weights)
        freed = 0.0
        over = set()
        for members in clusters.values():
            total = sum(out.get(m, 0.0) for m in members)
            if len(members) >= 2 and total > max_cluster_weight and total > 0:
                scale = max_cluster_weight / total
                for m in members:
                    new = out.get(m, 0.0) * scale
                    freed += out.get(m, 0.0) - new
                    out[m] = new
                over.update(members)

        if freed <= 1e-12:
            return out

        receivers = [n for n in out if n not in over]
        recv_total = sum(out[n] for n in receivers)
        if receivers and recv_total > 0:
            for n in receivers:
                out[n] += freed * (out[n] / recv_total)
        # else: nothing uncorrelated to move it to -- renormalise below

        s = sum(out.values())
        if s > 0:
            out = {k: v / s for k, v in out.items()}
        return out
    except Exception as exc:  # noqa: BLE001 -- fail-open
        LOG.warning("cluster rescaling failed (%s), leaving weights unchanged", exc)
        return dict(weights)


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
