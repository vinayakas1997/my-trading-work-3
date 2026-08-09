"""kalman_filters' own walk-forward backtest glue code.

Not a forecaster -- filtered_trend's sign is repurposed as a directional
signal, per the decided design. The one hard rule this file is built
around: **only `filtered_state` (causal) is ever used inside the
walk-forward step**. `smoothed_state` uses the whole series (a backward
pass), so using it mid-backtest would leak future information into a
"prediction" that's supposed to be causal -- a real correctness bug, not
a style choice. Smoothed state is exposed only through
`run_smoothed_diagnostic()`, a separate, whole-history-only function that
never feeds into a walk-forward row. No weights store: classical fit,
nothing trained.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.kalman_filters.compute import (
    MIN_OBSERVATIONS,
    _fit,
    _filtered_fields,
    _smoothed_fields,
)
from vinu_tools.compute.backtest.walk_forward import (
    StepResult,
    WalkForwardStep,
    run_walk_forward,
    run_walk_forward_parallel,
)


def _direction(value: float, eps: float = 1e-4) -> str:
    if value > eps:
        return "up"
    if value < -eps:
        return "down"
    return "flat"


def kalman_step(step: WalkForwardStep) -> StepResult:
    close = step.history["close"].astype(float).values
    try:
        res = _fit(close)
    except ValueError:
        return StepResult(row={"status": "fit_failed", "n_observations": int(len(close))})

    fields = _filtered_fields(res, len(close))  # filtered (causal) only -- never smoothed here
    predicted_direction = _direction(fields["filtered_trend"])

    actual_price = float(step.future.iloc[0]["close"])
    last_close = close[-1]
    actual_return = (actual_price - last_close) / last_close if last_close else 0.0
    actual_direction = _direction(actual_return)

    row = {
        **fields,
        "predicted_direction": predicted_direction,
        "actual_price": actual_price,
        "actual_direction": actual_direction,
        "hit": int(predicted_direction == actual_direction),
    }
    return StepResult(row=row)


def run_kalman_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    *,
    parallel: bool = False,
    chunk_size: int = 200,
    n_workers: int | None = None,
) -> pd.DataFrame:
    """parallel=True dispatches to run_walk_forward_parallel instead of the
    sequential loop -- safe here because this angle already refits every
    step (refit_cadence=1, no cross-step state reuse) with a fixed
    window=MIN_OBSERVATIONS context, so chunked execution is row-for-row
    identical to the sequential path."""
    if parallel:
        return run_walk_forward_parallel(
            symbol,
            timeframe,
            bars,
            kalman_step,
            min_observations=MIN_OBSERVATIONS,
            window=MIN_OBSERVATIONS,
            tag_fn=tag_row,
            chunk_size=chunk_size,
            n_workers=n_workers,
        )
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        kalman_step,
        min_observations=MIN_OBSERVATIONS,
        refit_cadence=1,  # real benchmark: fit is cheap (~0.026s), no cadence trick needed
        window=MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )


def run_smoothed_diagnostic(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    """Whole-history-only diagnostic: one row per symbol/timeframe, the
    two-pass smoothed terminal state over the *entire* available range --
    never tagged, never sliced, never fed into the causal backtest above.
    A hindsight "ground truth" trend estimate to compare filtered_trend
    against after the fact.
    """
    close = bars["close"].astype(float).dropna().values
    if len(close) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "insufficient_data",
            "n_observations": int(len(close)),
        }])
    try:
        res = _fit(close)
    except ValueError:
        return pd.DataFrame([{
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "fit_failed",
            "n_observations": int(len(close)),
        }])
    row = {
        "symbol": symbol,
        "timeframe": timeframe,
        "status": "ok",
        "n_observations": int(len(close)),
        **_smoothed_fields(res),
    }
    return pd.DataFrame([row])
