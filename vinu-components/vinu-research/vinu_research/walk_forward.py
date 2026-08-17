from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import NormalDist
from typing import Any
import numpy as np
import pandas as pd

LOG = logging.getLogger(__name__)

from vinu_simulator.engine.inference import (
    deflated_sharpe_ratio as _deflated_sharpe_ratio,
)

_STANDARD_NORMAL = NormalDist()
_EULER_GAMMA = 0.5772156649015329


@dataclass
class WalkForwardConfig:
    method: str = "expanding"
    train_pct: float = 0.6
    val_pct: float = 0.2
    test_pct: float = 0.2
    n_windows: int = 3
    min_train_days: int = 252
    step_size_days: int = 63
    gap_days: int = 5


@dataclass
class WalkForwardWindow:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str


class WindowSplitter:
    def __init__(self, config: WalkForwardConfig):
        self.config = config

    def split(self, from_date: str, to_date: str) -> list[WalkForwardWindow]:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        total_days = (to_dt - from_dt).days

        if total_days < self.config.min_train_days or self.config.n_windows <= 0:
            return []

        # Determine OOS test size
        test_size = int(total_days * self.config.test_pct)
        # Ensure test_size is at least 1 day
        test_size = max(test_size, 1)

        # Guard against date underflow and check configuration feasibility
        min_required_days = self.config.n_windows * test_size + self.config.gap_days + self.config.min_train_days
        if total_days < min_required_days:
            return []

        windows: list[WalkForwardWindow] = []
        for i in range(self.config.n_windows):
            # Calculate test window by working backward from to_dt
            # so that the last window's test ends exactly at to_dt
            test_end_dt = to_dt - timedelta(days=(self.config.n_windows - 1 - i) * test_size)
            test_start_dt = test_end_dt - timedelta(days=test_size)
            
            if test_start_dt <= from_dt:
                continue
                
            train_end_dt = test_start_dt - timedelta(days=self.config.gap_days)
            
            if self.config.method == "expanding":
                train_start_dt = from_dt
            else: # sliding
                train_size = int(total_days * self.config.train_pct)
                train_start_dt = train_end_dt - timedelta(days=train_size)
                
            if train_start_dt < from_dt:
                # Fallback: slide start can't go before from_dt
                train_start_dt = from_dt
                
            train_size_days = (train_end_dt - train_start_dt).days
            if train_size_days < self.config.min_train_days:
                continue

            windows.append(
                WalkForwardWindow(
                    window_id=len(windows) + 1,
                    train_start=train_start_dt.strftime("%Y-%m-%d"),
                    train_end=train_end_dt.strftime("%Y-%m-%d"),
                    test_start=test_start_dt.strftime("%Y-%m-%d"),
                    test_end=test_end_dt.strftime("%Y-%m-%d"),
                )
            )

        return windows


def aggregate_metrics(
    is_metrics_list: list[dict[str, float]],
    oos_metrics_list: list[dict[str, float]],
) -> tuple[dict[str, float], dict[str, float]]:
    if not is_metrics_list or not oos_metrics_list:
        return {}, {}

    is_aggregated: dict[str, float] = {}
    oos_aggregated: dict[str, float] = {}

    for key in is_metrics_list[0]:
        values = [m.get(key, 0.0) for m in is_metrics_list]
        is_aggregated[key] = float(np.median(values))
        is_aggregated[f"{key}_std"] = float(np.std(values)) if len(values) > 1 else 0.0

    for key in oos_metrics_list[0]:
        values = [m.get(key, 0.0) for m in oos_metrics_list]
        oos_aggregated[key] = float(np.median(values))
        oos_aggregated[f"{key}_std"] = float(np.std(values)) if len(values) > 1 else 0.0

    oos_returns = [m.get("total_return", 0.0) for m in oos_metrics_list]
    oos_aggregated["losing_window_fraction"] = float(
        sum(1 for r in oos_returns if r < 0) / len(oos_returns)
    )

    return is_aggregated, oos_aggregated


def deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
    periods_per_year: float = 252.0,
) -> float:
    """
    Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio: the probability that the
    observed Sharpe ratio reflects genuine skill after accounting for having been
    selected as the best of `n_trials` independent backtests run against the same
    data (e.g. LLM candidates, or repeated refinement iterations).

    Despite the name this returns a probability in [0, 1], not a Sharpe ratio.
    ~0.5 means "indistinguishable from what pure luck would produce by trying this
    many strategies" — not "mediocre." Values need to clear roughly 0.95 to be
    treated as evidence of real skill under the standard multiple-testing correction.

    `excess_kurtosis` follows the pandas/numpy convention (0.0 for a normal
    distribution), matching `BacktestMetrics.kurtosis`.

    Note: the canonical implementation lives in
    ``vinu_simulator.engine.inference.deflated_sharpe_ratio``.  This
    wrapper is kept for backward compatibility.
    """
    return _deflated_sharpe_ratio(
        sharpe=sharpe,
        n_trials=n_trials,
        n_obs=n_obs,
        skew=skew,
        excess_kurtosis=excess_kurtosis,
        periods_per_year=periods_per_year,
    )


# ---------------------------------------------------------------------------
# Implementation-plan task 06 (shortcoming #8): parameter-re-optimizing
# walk-forward for the RECIPE/grid path, alongside the snapshot walk-forward
# the research loop's _run_walk_forward already runs for raw-code strategies.
# PBO estimates the odds the top Sharpe is an in-sample artifact; walk-forward
# re-optimizes parameters on each rolling train window and checks whether the
# winning parameters AND their out-of-sample performance hold up window to
# window -- a complementary failure mode. Ported from Jarvis/core/backtesting/
# walk_forward.py's rolling re-optimization idea (robustness ratio /
# overfitting score), expressed as a Sharpe-gap + OOS-positivity + parameter-
# agreement stability verdict, and sharing the WindowSplitter above.
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardRunWindow:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: dict[str, float]
    in_sample_metrics: dict[str, float]
    out_of_sample_metrics: dict[str, float]


@dataclass
class WalkForwardRunResult:
    """A parameter-re-optimizing walk-forward pass over a recipe/base-code
    param grid. `n_planned` is the number of windows the splitter produced;
    `n_completed` is how many actually finished both a train-grid
    re-optimization and an out-of-sample backtest -- the sweep-engine
    `completeness` pattern, so a partially-failed run can't masquerade as a
    clean pass. `parameter_agreement` is the fraction of completed windows
    whose re-optimized best params matched the modal best-param set across
    windows (how stable the "optimal" parameters actually are)."""

    n_planned: int
    n_completed: int
    completeness: float
    method: str
    windows: list[WalkForwardRunWindow]
    aggregated_is_metrics: dict[str, float]
    aggregated_oos_metrics: dict[str, float]
    sharpe_gap: float
    oos_positive_window_fraction: float
    parameter_agreement: float
    stability_verdict: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_planned": self.n_planned,
            "n_completed": self.n_completed,
            "completeness": self.completeness,
            "method": self.method,
            "sharpe_gap": round(self.sharpe_gap, 4),
            "oos_positive_window_fraction": round(self.oos_positive_window_fraction, 4),
            "parameter_agreement": round(self.parameter_agreement, 4),
            "stability_verdict": self.stability_verdict,
            "windows": [
                {
                    "window_id": w.window_id,
                    "train_start": w.train_start,
                    "train_end": w.train_end,
                    "test_start": w.test_start,
                    "test_end": w.test_end,
                    "best_params": w.best_params,
                    "in_sample_metrics": w.in_sample_metrics,
                    "out_of_sample_metrics": w.out_of_sample_metrics,
                }
                for w in self.windows
            ],
        }


def evaluate_walk_forward_stability(
    *,
    sharpe_gap: float,
    oos_positive_window_fraction: float,
    n_completed: int,
    n_planned: int,
    threshold: float,
    min_completed_windows: int,
) -> dict[str, Any]:
    """Deterministic PASS/FAIL for a parameter-re-optimizing walk-forward
    pass -- the signal the recipe path's self-verdict reads alongside PBO
    (implementation-plan task 06). Fail-closed: an incomplete pass, too few
    completed windows, a Sharpe gap past the (configurable) threshold, or
    fewer than half the out-of-sample windows actually profitable all push
    toward FAIL -- never a lenient PASS off one lucky window.

    Returns {"passed": bool, "reasons": [..]}, reasons empty only when the
    pass is clean."""
    reasons: list[str] = []
    if n_planned > 0 and n_completed < n_planned:
        reasons.append(
            f"incomplete walk-forward: {n_completed}/{n_planned} windows completed"
        )
    if n_completed < min_completed_windows:
        reasons.append(
            f"too few completed windows ({n_completed} < {min_completed_windows})"
        )
    if sharpe_gap > threshold:
        reasons.append(f"Sharpe gap {sharpe_gap:.2f} exceeds threshold {threshold:.2f}")
    if oos_positive_window_fraction < 0.5:
        reasons.append(
            f"only {oos_positive_window_fraction:.0%} of out-of-sample windows had positive Sharpe"
        )
    return {"passed": not reasons, "reasons": reasons or ["walk-forward stability within tolerance"]}


async def run_walk_forward(
    *,
    symbol: str,
    from_date: str,
    to_date: str,
    param_grid: list[dict[str, Any]],
    recipe: str | None = None,
    base_code: str | None = None,
    param_name: str | None = None,
    indicators: list[str] | None = None,
    initial_capital: float | None = None,
    config: Any = None,
    tools: Any = None,
) -> WalkForwardRunResult | None:
    """Re-optimizing walk-forward over a param grid, sharing the exact same
    execution path as run_sweep_grid (run_sweep_grid -> run_sweep_candidate
    -> the real simulator backtest).

    For each rolling window the splitter produces: re-optimize the grid on
    the window's TRAIN slice (the top-ranked candidate's params are that
    window's "optimal" params), then backtest THOSE params on the window's
    out-of-sample slice. The stability verdict then asks the two questions
    PBO can't answer alone: do the winning parameters hold up window to
    window (parameter_agreement), and does their out-of-sample performance
    stay positive and near in-sample (Sharpe gap / OOS positivity)?

    Returns None when there isn't enough data for even one window (the
    same "not enough data" posture as the loop's snapshot walk-forward) --
    a null result is informative (the caller says so), never a clean pass.
    """
    from vinu_research.config import ResearchConfig
    from vinu_research.sweep_grid import run_sweep_grid
    from vinu_research.sweep import run_sweep_candidate
    from vinu_research.tools import ResearchTools

    cfg = config or ResearchConfig()
    resolved_tools = tools or ResearchTools(cfg)
    wf_config = WalkForwardConfig(
        method=cfg.walk_forward_method,
        train_pct=cfg.walk_forward_train_pct,
        test_pct=cfg.walk_forward_test_pct,
        n_windows=cfg.walk_forward_windows,
        min_train_days=cfg.walk_forward_min_train_days,
        step_size_days=cfg.walk_forward_step_size_days,
        gap_days=cfg.walk_forward_gap_days,
    )
    splitter = WindowSplitter(wf_config)
    windows = splitter.split(from_date, to_date)
    if not windows:
        LOG.warning("Walk-forward: not enough data for %d windows", wf_config.n_windows)
        return None

    # Inner window grids must not recursively trigger their own walk-
    # forward -- run_sweep_grid gates it on config.walk_forward_enabled.
    import dataclasses

    inner_config = dataclasses.replace(cfg, walk_forward_enabled=False)

    completed: list[WalkForwardRunWindow] = []
    for w in windows:
        try:
            grid = await run_sweep_grid(
                symbol=symbol, from_date=w.train_start, to_date=w.train_end,
                param_grid=param_grid, recipe=recipe, base_code=base_code,
                param_name=param_name, indicators=indicators,
                initial_capital=initial_capital, config=inner_config,
                tools=resolved_tools,
            )
            if not grid.ranked:
                LOG.warning(
                    "walk-forward window %d: no candidate succeeded on the train slice, window incomplete",
                    w.window_id,
                )
                continue
            best = grid.ranked[0]
            best_params = best.params
            if recipe is not None:
                test_result = await run_sweep_candidate(
                    symbol=symbol, from_date=w.test_start, to_date=w.test_end,
                    recipe=recipe, params=best_params,
                    indicators=indicators, initial_capital=initial_capital,
                    tools=resolved_tools,
                )
            else:
                if param_name is None or param_name not in best_params:
                    continue
                test_result = await run_sweep_candidate(
                    symbol=symbol, from_date=w.test_start, to_date=w.test_end,
                    base_code=base_code, param_name=param_name,
                    param_value=best_params[param_name],
                    indicators=indicators, initial_capital=initial_capital,
                    tools=resolved_tools,
                )
            completed.append(WalkForwardRunWindow(
                window_id=w.window_id,
                train_start=w.train_start,
                train_end=w.train_end,
                test_start=w.test_start,
                test_end=w.test_end,
                best_params=best_params,
                in_sample_metrics=best.sweep_result.metrics,
                out_of_sample_metrics=test_result.metrics,
            ))
        except Exception:
            LOG.exception(
                "walk-forward window %d failed, window incomplete", w.window_id,
            )

    if not completed:
        return None

    is_list = [w.in_sample_metrics for w in completed]
    oos_list = [w.out_of_sample_metrics for w in completed]
    aggregated_is, aggregated_oos = aggregate_metrics(is_list, oos_list)

    is_sharpe = aggregated_is.get("sharpe_ratio", 0.0)
    oos_sharpe = aggregated_oos.get("sharpe_ratio", 0.0)
    sharpe_gap = is_sharpe - oos_sharpe
    oos_positive = sum(1 for m in oos_list if m.get("sharpe_ratio", 0.0) > 0.0) / len(oos_list)

    from collections import Counter

    param_sets = Counter(frozenset(p.items()) for p in [w.best_params for w in completed])
    modal_count = param_sets.most_common(1)[0][1] if param_sets else 0
    parameter_agreement = modal_count / len(completed)

    n_planned = len(windows)
    n_completed = len(completed)
    verdict = evaluate_walk_forward_stability(
        sharpe_gap=sharpe_gap,
        oos_positive_window_fraction=oos_positive,
        n_completed=n_completed,
        n_planned=n_planned,
        threshold=cfg.walk_forward_stability_threshold,
        min_completed_windows=cfg.walk_forward_min_completed_windows,
    )
    LOG.info(
        "Walk-forward: IS Sharpe=%.2f OOS Sharpe=%.2f gap=%.2f, %d/%d windows, "
        "param agreement=%.0f%%, verdict=%s",
        is_sharpe, oos_sharpe, sharpe_gap, n_completed, n_planned,
        parameter_agreement * 100.0, verdict["passed"],
    )

    return WalkForwardRunResult(
        n_planned=n_planned,
        n_completed=n_completed,
        completeness=n_completed / n_planned if n_planned else 0.0,
        method=cfg.walk_forward_method,
        windows=completed,
        aggregated_is_metrics=aggregated_is,
        aggregated_oos_metrics=aggregated_oos,
        sharpe_gap=sharpe_gap,
        oos_positive_window_fraction=oos_positive,
        parameter_agreement=parameter_agreement,
        stability_verdict=verdict,
    )
