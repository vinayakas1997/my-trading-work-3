"""Naive baseline for kalman_filters -- deliberately NOT the "forecast =
last close, RMSE/MAE" pattern used for ARIMA/DLinear/etc. This angle has
no price forecast at all (filtered_level is a state estimate, not "next
price"), only a directional signal -- so there's no forecast_price to
compute RMSE against.

The decided design's own worked example (04-enhancement-of-each-angle/
10-kalman_filters.md SS4) illustrates a *directional-accuracy* naive
baseline ("~51.2%"), not an error metric. A "predict flat" naive model
(the DLinear/iTransformer pattern) would be degenerate here for the
identical reason it was dropped there -- real markets essentially never
close exactly flat, so it would score near 0%, not ~51%. The naive
baseline used here instead is **persistence**: predict the next move
continues the same direction as the most recently realized move -- the
standard, non-degenerate directional baseline, and the one that actually
produces a real ~50%-ish hit rate matching the design doc's own
illustrative number.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.kalman_filters.backtest import _direction
from vinu_initial_analysis.angles.kalman_filters.compute import MIN_OBSERVATIONS
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def naive_step(step: WalkForwardStep) -> StepResult:
    close = step.history["close"].astype(float).values
    last_close = float(close[-1])
    prior_close = float(close[-2]) if len(close) > 1 else last_close
    last_realized_return = (last_close - prior_close) / prior_close if prior_close else 0.0
    predicted_direction = _direction(last_realized_return)

    actual_price = float(step.future.iloc[0]["close"])
    actual_return = (actual_price - last_close) / last_close if last_close else 0.0
    actual_direction = _direction(actual_return)

    row = {
        "status": "ok",
        "n_observations": int(len(close)),
        "predicted_direction": predicted_direction,
        "actual_price": actual_price,
        "actual_direction": actual_direction,
        "hit": int(predicted_direction == actual_direction),
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
