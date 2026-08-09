"""Naive random-walk baseline for iTransformer: forecast = last_close.

RMSE/MAE only, same pattern as ARIMA/Chronos/exponential_smoothing's
naive baselines -- not a direction-hit comparison. A constant "no
change" forecast is always "flat," so comparing that against real
market moves (which are essentially never exactly flat) isn't a
meaningful hit-rate comparison, it would just measure how often the
market genuinely didn't move. abs_error/squared_error are directly
comparable to iTransformer's own fields of the same name.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.itransformer.compute import MIN_BARS
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    last_close = float(step.history["close"].iloc[-1])
    actual_price = float(step.future.iloc[0]["close"])
    row = {
        "status": "ok",
        "n_observations": int(len(step.history)),
        "forecast_price": last_close,
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
        min_observations=MIN_BARS,
        tag_fn=tag_row,
    )
