"""Naive random-walk baseline for TFT: forecast = last_close.
RMSE/MAE only, no direction-hit/in_band field -- same reasoning as every
other DLinear-family angle's naive baseline (a constant "no change"
forecast has no meaningful band to check coverage against).
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.tft.compute import MIN_BARS
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    last_close = float(step.history["close"].iloc[-1])
    actual_price = float(step.future.iloc[0]["close"])
    row = {
        "status": "ok",
        "n_observations": int(len(step.history)),
        "forecast_price": last_close,
        "actual_price": actual_price,
        "close_abs_error": abs(actual_price - last_close),
        "close_sq_error": (actual_price - last_close) ** 2,
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
        min_observations=MIN_BARS,
        tag_fn=tag_row,
    )
