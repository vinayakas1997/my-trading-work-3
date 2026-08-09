"""Naive random-walk baseline for Chronos, run through the same
walk-forward harness -- "does Chronos actually beat doing nothing,"
same rationale as ARIMA's naive baseline. Extended to Chronos's 5-step
horizon: forecast = last_close for every step (a flat line), scored on
RMSE/MAE per step, directly comparable to Chronos's own median-forecast
error at that same step. No p10/p90-coverage metric for the naive
model, for the same reason ARIMA's naive baseline doesn't have one -- a
constant forecast has no meaningful confidence band to check coverage
against.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.chronos.backtest import HORIZON
from vinu_initial_analysis.angles.chronos.compute import MIN_OBSERVATIONS
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    last_close = float(step.history["close"].iloc[-1])
    predictions: dict[str, dict] = {}  # string keys -- see backtest.py's chronos_step for why
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        predictions[str(h + 1)] = {
            "forecast": last_close,
            "actual": actual_price,
            "abs_error": abs(actual_price - last_close),
            "squared_error": (actual_price - last_close) ** 2,
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
        min_observations=MIN_OBSERVATIONS,
        horizon=HORIZON,
        window=MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )
