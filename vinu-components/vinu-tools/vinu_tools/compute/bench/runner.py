"""Unified bench runner: compute factors, run IC analysis, classify as ALIVE/REVERSED/DEAD.

Usage:
    from vinu_tools.compute.bench import bench_factor, bench_factors, bench_zoo

    # Single factor
    result = bench_factor("gtja191_001", panel)

    # Multiple factors by ID
    results = bench_factors(["gtja191_001", "alpha101_001"], panel)

    # Entire factor group
    results = bench_zoo("gtja191", panel)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from vinu_tools.compute.formulas.engine import compute_factor, resolve_factor_spec
from vinu_tools.compute.registry import get_alpha_registry

LOG = logging.getLogger(__name__)


def _compute_forward_returns(
    panel: dict[str, pd.DataFrame],
    forward_days: int = 1,
) -> pd.DataFrame:
    """Compute forward returns from close prices in panel.

    Args:
        panel: dict with "close" as T x N DataFrame.
        forward_days: Number of periods forward.

    Returns:
        T x N DataFrame of forward returns, NaN for last row.
    """
    close = panel.get("close")
    if close is None:
        raise ValueError("Panel must contain 'close' for forward returns")
    returns = close.pct_change(forward_days).shift(-forward_days)
    return returns


def _panel_to_1d(
    factor_df: pd.DataFrame,
    forward_df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Flatten T x N factor and forward return DataFrames to 1D arrays.

    Drops NaN pairs and returns aligned arrays.
    """
    fv = factor_df.values.flatten()
    fr = forward_df.values.flatten()
    valid = ~(np.isnan(fv) | np.isnan(fr))
    return fv[valid], fr[valid]


def bench_factor(
    factor_id: str,
    panel: dict[str, pd.DataFrame],
    forward_days: int = 1,
    min_periods: int = 20,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Benchmark a single factor: compute value, measure IC, classify.

    Args:
        factor_id: e.g. "gtja191_001", "alpha101_001"
        panel: dict of {column: pd.DataFrame(T x N)}
        forward_days: Forward return horizon in periods.
        min_periods: Minimum aligned periods required.
        params: Optional param overrides (e.g. {"lag": 8}).

    Returns:
        dict with status, ic_mean, ic_positive_ratio, t_stat, plus YAML metadata.
    """
    spec = resolve_factor_spec(factor_id) or {}
    columns_required = spec.get("columns_required", ["close"])

    missing = [c for c in columns_required if c not in panel]
    if missing:
        return {
            "id": factor_id,
            "status": "missing_columns",
            "missing_columns": missing,
            "theme": spec.get("theme", []),
            "description": spec.get("description", ""),
        }

    try:
        factor_values = compute_factor(factor_id, panel, params=params or {})
    except Exception as e:
        LOG.warning("compute_factor %s failed: %s", factor_id, e)
        return {
            "id": factor_id,
            "status": "compute_error",
            "error": str(e),
            "theme": spec.get("theme", []),
            "description": spec.get("description", ""),
        }

    forward_returns = _compute_forward_returns(panel, forward_days)

    fv_1d, fr_1d = _panel_to_1d(factor_values, forward_returns)

    bench_result = run_bench(
        {factor_id: fv_1d},
        fr_1d,
        min_periods=min_periods,
    )[factor_id]

    bench_result["id"] = factor_id
    bench_result["theme"] = spec.get("theme", [])
    bench_result["description"] = spec.get("description", "")
    bench_result["interpretation"] = spec.get("interpretation", "")
    bench_result["params"] = spec.get("params", {})
    bench_result["decay_horizon"] = spec.get("decay_horizon", 0)
    bench_result["columns_required"] = columns_required

    return bench_result


def bench_factors(
    factor_ids: list[str],
    panel: dict[str, pd.DataFrame],
    forward_days: int = 1,
    min_periods: int = 20,
) -> list[dict[str, Any]]:
    """Benchmark multiple factors by ID.

    Args:
        factor_ids: List of factor IDs to evaluate.
        panel: dict of {column: pd.DataFrame(T x N)}
        forward_days: Forward return horizon.
        min_periods: Minimum periods required.

    Returns:
        List of result dicts sorted by |IC| descending.
    """
    results = []
    for fid in factor_ids:
        try:
            result = bench_factor(fid, panel, forward_days, min_periods)
            results.append(result)
        except Exception as e:
            LOG.warning("bench_factor %s failed: %s", fid, e)
            results.append({
                "id": fid,
                "status": "error",
                "error": str(e),
            })

    results.sort(key=lambda r: abs(r.get("ic_mean", 0) if r.get("ic_mean") is not None else 0), reverse=True)
    return results


def bench_zoo(
    zoo: str,
    panel: dict[str, pd.DataFrame],
    forward_days: int = 1,
    min_periods: int = 20,
    max_factors: int | None = None,
) -> list[dict[str, Any]]:
    """Benchmark all factors in a zoo group.

    Args:
        zoo: Group name — "gtja191", "alpha101", "academic", "fundamental".
        panel: dict of {column: pd.DataFrame(T x N)}
        forward_days: Forward return horizon.
        min_periods: Minimum periods required.
        max_factors: Limit to N factors (for quick testing).

    Returns:
        List of result dicts sorted by |IC| descending.
    """
    reg = get_alpha_registry()
    all_alphas = reg.list_alphas()

    zoo_ids = [
        a.meta.id for a in all_alphas
        if a.meta.id.startswith(zoo.rstrip("0123456789_"))
    ]
    zoo_ids = sorted(zoo_ids)

    if max_factors:
        zoo_ids = zoo_ids[:max_factors]

    LOG.info("Benchmarking zoo=%s with %d factors", zoo, len(zoo_ids))
    return bench_factors(zoo_ids, panel, forward_days, min_periods)


# ── Core IC analysis (moved from compute/alpha_bench.py) ───────


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
