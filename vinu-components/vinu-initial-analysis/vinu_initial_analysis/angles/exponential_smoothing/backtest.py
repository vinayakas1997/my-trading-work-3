"""exponential_smoothing's own walk-forward backtest glue code.

Group A, structurally close to DLinear: a point forecast with no
confidence interval, so the hit definition is direction-match, not
CI-coverage. Refits every single step at every timeframe -- a real
benchmark (see compute.py's _fit_and_forecast docstring) showed a single
fit costs ~0.014s, negligible even at 1-minute resolution, and
ExponentialSmoothingResults has no `.append()` incremental-refit path the
way ARIMA's does, so there's nothing to skip anyway. No weights store --
nothing is trained in the neural-net sense (Holt's method is a classical
statistical fit).
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.exponential_smoothing.compute import MIN_OBSERVATIONS, _fit_and_forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def _direction(value: float, eps: float = 1e-4) -> str:
    if value > eps:
        return "up"
    if value < -eps:
        return "down"
    return "flat"


def es_step(step: WalkForwardStep) -> StepResult:
    close = step.history["close"].astype(float).values
    try:
        fields, _res = _fit_and_forecast(close)
    except ValueError:
        return StepResult(row={"status": "fit_failed", "n_observations": int(len(close))})

    last_close = float(close[-1])
    forecast_return = (fields["forecast"] - last_close) / last_close if last_close else 0.0
    predicted_direction = _direction(forecast_return)

    actual_price = float(step.future.iloc[0]["close"])
    actual_return = (actual_price - last_close) / last_close if last_close else 0.0
    actual_direction = _direction(actual_return)

    row = {
        **fields,
        "predicted_direction": predicted_direction,
        "actual_price": actual_price,
        "actual_direction": actual_direction,
        "hit": int(predicted_direction == actual_direction),
        "abs_error": abs(actual_price - fields["forecast"]),
        "squared_error": (actual_price - fields["forecast"]) ** 2,
    }
    return StepResult(row=row)


def run_es_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        es_step,
        min_observations=MIN_OBSERVATIONS,
        refit_cadence=1,  # real benchmark: fit is cheap (~0.014s), no cadence trick needed
        window=MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )
