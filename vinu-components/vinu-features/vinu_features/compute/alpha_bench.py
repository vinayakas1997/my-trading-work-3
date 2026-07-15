from __future__ import annotations

import logging
from typing import Any

import numpy as np

LOG = logging.getLogger(__name__)


def run_bench(
    alpha_values: dict[str, np.ndarray],
    forward_returns: np.ndarray,
    min_periods: int = 20,
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for alpha_id, values in alpha_values.items():
        aligned = ~(np.isnan(values) | np.isnan(forward_returns))
        valid_count = aligned.sum()
        if valid_count < min_periods:
            results[alpha_id] = {
                "status": "insufficient_data",
                "n_periods": int(valid_count),
            }
            continue

        v = values[aligned]
        fwd = forward_returns[aligned]

        ic = np.corrcoef(v, fwd)[0, 1] if len(v) > 2 else 0.0
        ic = ic if not np.isnan(ic) else 0.0

        ic_positive_ratio = float(np.mean(v * fwd > 0))
        n_periods = len(v)

        from scipy import stats as scipy_stats
        t_stat, _ = scipy_stats.ttest_ind(fwd[v > 0], fwd[v <= 0]) if (v > 0).any() and (v <= 0).any() else (0.0, 1.0)
        t_stat = t_stat if not np.isnan(t_stat) else 0.0

        if ic > 0.02 and ic_positive_ratio >= 0.55 and abs(t_stat) > 2:
            status = "alive"
        elif ic < -0.02 and abs(t_stat) > 2:
            status = "reversed"
        else:
            status = "dead"

        results[alpha_id] = {
            "status": status,
            "ic_mean": float(ic),
            "ic_positive_ratio": float(ic_positive_ratio),
            "t_stat": float(t_stat),
            "n_periods": int(n_periods),
        }

    return results


def run_compare(
    alpha_values: dict[str, np.ndarray],
    forward_returns: np.ndarray,
    only: list[str] | None = None,
    min_periods: int = 20,
) -> list[dict[str, Any]]:
    if only is not None:
        alpha_values = {k: v for k, v in alpha_values.items() if k in only}
    results = run_bench(alpha_values, forward_returns, min_periods)
    ranked = [
        {"alpha_id": k, **v}
        for k, v in results.items()
        if v.get("status") != "insufficient_data"
    ]
    ranked.sort(key=lambda x: abs(x.get("ic_mean", 0)), reverse=True)
    return ranked
