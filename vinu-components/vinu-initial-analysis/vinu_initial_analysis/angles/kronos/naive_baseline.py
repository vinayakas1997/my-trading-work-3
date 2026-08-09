"""Naive random-walk baseline for Kronos, run through the same
walk-forward harness -- same pattern as Chronos's naive baseline
(forecast = last_close for every horizon step, RMSE/MAE-only, no
CI/hit-coverage metric since a constant forecast has no meaningful band
or direction of its own).
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.kronos.backtest import WALK_FORWARD_MIN_OBSERVATIONS
from vinu_initial_analysis.angles.kronos.compute import HORIZON
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    last_close = float(step.history["close"].iloc[-1])
    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_close = float(step.future.iloc[h]["close"])
        predictions[str(h + 1)] = {
            "close": last_close,
            "actual_close": actual_close,
            "close_sq_error": (actual_close - last_close) ** 2,
        }
    return StepResult(row={"status": "ok", "predictions": predictions})


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
        min_observations=WALK_FORWARD_MIN_OBSERVATIONS,
        horizon=HORIZON,
        window=WALK_FORWARD_MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )
