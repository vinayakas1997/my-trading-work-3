from __future__ import annotations

import math
from itertools import combinations

import numpy as np


def _logit(p: float) -> float:
    p = max(min(p, 1 - 1e-15), 1e-15)
    return float(math.log(p / (1 - p)))


def probability_of_backtest_overfitting(
    returns_matrix: np.ndarray,
    n_splits: int = 16,
    n_combinations: int | None = None,
    metric: str = "sharpe",
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """
    Bailey, Borwein, Lopez de Prado & Zhu (2017) Probability of Backtest
    Overfitting (PBO) via Combinatorially Symmetric Cross-Validation
    (CSCV).

    Why this matters:
        When multiple strategy variants are tested on the same data, the
        best-performing one is likely overfit — it won by chance, not
        skill.  PBO measures how often the in-sample (IS) winning
        strategy ends up below median in out-of-sample (OOS) data.
        A high PBO means the selection process is overfit; a low PBO
        means the IS winner tends to stay a winner OOS.

    Algorithm (CSCV):
        1. Split the *T* time periods into *S* contiguous blocks.
        2. For each way to assign S/2 blocks to IS and S/2 to OOS:
           a. Compute the performance metric (e.g. Sharpe) for each
              strategy on the IS block set.
           b. Rank the strategies IS; note the rank of the IS-best
              strategy on the OOS block set.
        3. The rank is converted to a logit: logit = log(r / (N - r)).
        4. PBO = fraction of splits where the logit > 0 (i.e. the
           IS-best strategy ranks below median OOS).

    Interpretation:
        PBO < 0.30  → low overfitting; the selection process has
                       genuine information.
        PBO ~ 0.50  → coin flip; selection is uninformative.
        PBO > 0.70  → severe overfitting; IS winners tend to lose OOS.

    References:
        Bailey, D.H., Borwein, J., Lopez de Prado, M. & Zhu, Q.J.
            (2017). "The Probability of Backtest Overfitting." Journal
            of Computational Finance, 20(4), 39-69.
        Lopez de Prado, M. (2018). "Advances in Financial Machine
            Learning." Wiley, Chapter 11.

    Parameters:
        returns_matrix: ndarray of shape (n_periods, n_strategies).
            Each column is one strategy's return series; each row is
            one time period.
        n_splits: number of time-series blocks (default 16).  Must be
            an even number >= 2.
        n_combinations: if set, limits to this many random IS/OOS
            pairings (Monte Carlo approximation).  Default None =
            all C(S, S/2) combinations.
        metric: performance metric — "sharpe" (default) or "mean".
        rng: optional ``np.random.Generator``.

    Returns:
        dict with keys:
            pbo: float — Probability of Backtest Overfitting [0, 1].
            logit_mean: float — mean logit across all splits.
            logit_std: float — std of logit across all splits.
            n_splits: int — number of time-series blocks.
            n_combinations: int — number of IS/OOS pairings evaluated.
            n_strategies: int.
            n_periods: int.
    """
    T, N = returns_matrix.shape
    if T < n_splits * 2 or N < 2:
        return {
            "pbo": 0.5,
            "logit_mean": 0.0,
            "logit_std": 0.0,
            "n_splits": n_splits,
            "n_combinations": 0,
            "n_strategies": N,
            "n_periods": T,
        }

    rng = rng or np.random.default_rng()

    # --- split indices into S contiguous blocks ---
    block_edges = np.linspace(0, T, n_splits + 1, dtype=int)
    blocks = [list(range(block_edges[i], block_edges[i + 1])) for i in range(n_splits)]

    all_splits = list(combinations(range(n_splits), n_splits // 2))

    if n_combinations is not None and len(all_splits) > n_combinations:
        all_splits = rng.choice(all_splits, size=n_combinations, replace=False)

    def _perf(x: np.ndarray) -> float:
        if metric == "mean":
            return float(np.mean(x))
        s = np.std(x, ddof=1)
        return float(np.mean(x) / s) if s > 0 else 0.0

    logits: list[float] = []

    for is_block_indices in all_splits:
        is_mask = np.zeros(T, dtype=bool)
        for bi in is_block_indices:
            is_mask[blocks[bi]] = True
        oos_mask = ~is_mask

        is_perf = np.array([_perf(returns_matrix[is_mask, j]) for j in range(N)])
        oos_perf = np.array([_perf(returns_matrix[oos_mask, j]) for j in range(N)])

        is_best_col = int(np.argmax(is_perf))
        oos_rank = int(np.sum(oos_perf > oos_perf[is_best_col]))

        logits.append(_logit((oos_rank + 1) / (N + 1)))

    logits_arr = np.array(logits)
    pbo = float(np.mean(logits_arr > 0))

    return {
        "pbo": pbo,
        "logit_mean": float(np.mean(logits_arr)),
        "logit_std": float(np.std(logits_arr, ddof=1)),
        "n_splits": n_splits,
        "n_combinations": len(logits),
        "n_strategies": N,
        "n_periods": T,
    }
