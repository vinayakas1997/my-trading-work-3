"""Generic single-symbol walk-forward backtest loop.

Slides through history one step at a time: at each point, hand the caller
everything knowable up to that point plus the next `horizon` actual bars to
score against, collect what the caller returns, move forward one step,
repeat. All angle-specific logic (how to forecast, what counts as a hit,
whether/what to train) lives in the caller's `step_fn` — this module only
owns window slicing, refit cadence, and wiring tags/weights onto the output
rows.

Generic on purpose: this lives in `vinu_tools` and must not import anything
from `vinu-initial-analysis` (see 05-storage-enhancement-levels/plan.md for
why — that would create a circular package dependency). Tagging and
weight-persistence are accepted as plain callables instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

import pandas as pd


@dataclass
class WalkForwardStep:
    step_index: int
    history: pd.DataFrame
    """Bars up to and including this step (bar_ts, close, ...), oldest first."""
    future: pd.DataFrame
    """The next `horizon` actual bars, for scoring the forecast against."""
    bar_ts: int
    """bar_ts of the last row in `history` — the point the forecast is made from."""
    is_refit_step: bool
    """False when refit_cadence > 1 and this step reuses `prior_state`."""
    prior_state: Any | None
    """Whatever the previous step's StepResult.state was, or None on the first step."""


@dataclass
class StepResult:
    row: dict[str, Any]
    """The angle's own fields only (forecast/CI/hit/...) — no tags, no weights_ref; those are added by the harness."""
    weights: Any | None = None
    state: Any | None = None
    """Carried forward as the next step's `prior_state`."""


StepFn = Callable[[WalkForwardStep], StepResult]
TagFn = Callable[[int], dict[str, Any]]
WeightsSink = Callable[[str, str, int, Any], str]


def run_walk_forward(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    step_fn: StepFn,
    *,
    min_observations: int,
    horizon: int = 1,
    refit_cadence: int = 1,
    window: Literal["expanding"] | int = "expanding",
    tag_fn: TagFn | None = None,
    weights_sink: WeightsSink | None = None,
) -> pd.DataFrame:
    """Runs a walk-forward backtest, returning one row per step.

    bars must have a `bar_ts` (int) column plus whatever price columns
    step_fn needs, sorted ascending. A step is only emitted once a full
    `horizon`-bar future window is available to score against — the final
    `horizon - 1` bars of `bars` never become decision points, since there
    isn't enough real future data left to check them against.

    Each output row = symbol/timeframe/bar_ts/step_index, merged with
    tag_fn(bar_ts) (if given), merged with step_fn's own row dict, plus
    weights_ref = weights_sink(symbol, timeframe, bar_ts, weights) when
    step_fn returns weights and a sink was provided.
    """
    if min_observations < 1:
        raise ValueError("min_observations must be >= 1")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    if refit_cadence < 1:
        raise ValueError("refit_cadence must be >= 1")

    n = len(bars)
    rows: list[dict[str, Any]] = []
    state: Any | None = None
    step_index = 0

    # position is the index (0-based) of the last bar included in `history`
    position = min_observations - 1
    while position < n and position + horizon < n:
        if isinstance(window, int):
            start = max(0, position + 1 - window)
        else:
            start = 0
        history = bars.iloc[start : position + 1]
        future = bars.iloc[position + 1 : position + 1 + horizon]
        bar_ts = int(history.iloc[-1]["bar_ts"])
        is_refit_step = step_index % refit_cadence == 0

        step = WalkForwardStep(
            step_index=step_index,
            history=history,
            future=future,
            bar_ts=bar_ts,
            is_refit_step=is_refit_step,
            prior_state=state,
        )
        result = step_fn(step)
        state = result.state

        row: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "bar_ts": bar_ts,
            "step_index": step_index,
        }
        if tag_fn is not None:
            row.update(tag_fn(bar_ts))
        row.update(result.row)
        if result.weights is not None and weights_sink is not None:
            row["weights_ref"] = weights_sink(symbol, timeframe, bar_ts, result.weights)

        rows.append(row)
        step_index += 1
        position += 1

    return pd.DataFrame(rows)
