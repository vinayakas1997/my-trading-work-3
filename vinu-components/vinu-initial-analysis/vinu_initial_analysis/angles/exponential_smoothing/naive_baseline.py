"""Naive random-walk baseline for exponential_smoothing, same
RMSE/MAE-only pattern as ARIMA's and Chronos's naive baselines -- "does
Holt's method actually beat doing nothing." No hit/direction metric: a
constant "no change" forecast is always "flat," so a direction-hit
comparison against it isn't measuring anything real.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.exponential_smoothing.compute import MIN_OBSERVATIONS
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    last_close = float(step.history["close"].iloc[-1])
    actual_price = float(step.future.iloc[0]["close"])
    row = {
        "status": "ok",
        "n_observations": int(len(step.history)),
        "forecast": last_close,
        "actual_price": actual_price,
        "abs_error": abs(actual_price - last_close),
        "squared_error": (actual_price - last_close) ** 2,
    }
    return StepResult(row=row)


def run_naive_baseline(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        naive_step,
        min_observations=MIN_OBSERVATIONS,
        window=MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )
