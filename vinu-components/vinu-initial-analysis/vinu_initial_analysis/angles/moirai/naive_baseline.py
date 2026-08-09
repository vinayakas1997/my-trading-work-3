"""Naive random-walk baseline for moirai, run through the same
walk-forward harness -- "does the AR(3) fallback proxy actually beat
doing nothing," same rationale as lag_llama's naive baseline. Flat
forecast (= last_close) over the same 5-step horizon, RMSE/MAE only --
no CI-coverage/pinball metric, a constant forecast has no quantile band
to score.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.moirai.compute import HORIZON, MIN_OBSERVATIONS
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
        tag_fn=tag_row,
    )
