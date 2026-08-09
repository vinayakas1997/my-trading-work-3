"""Naive random-walk baseline for timer_timerxl, run through the same
walk-forward harness -- "does Timer actually beat doing nothing," same
rationale as Chronos/Kronos's naive baselines. Extended to the 5-step
horizon: forecast = last_close for every step, scored on RMSE/MAE per
step. No in-band/hit metric for the naive model -- a constant forecast
has no meaningful confidence band or direction to check.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.timer_timerxl.backtest import HORIZON
from vinu_initial_analysis.angles.timer_timerxl.compute import MIN_OBSERVATIONS
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    last_close = float(step.history["close"].iloc[-1])
    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        predictions[str(h + 1)] = {
            "forecast": last_close,
            "actual": actual_price,
            "close_abs_error": abs(actual_price - last_close),
            "close_sq_error": (actual_price - last_close) ** 2,
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
