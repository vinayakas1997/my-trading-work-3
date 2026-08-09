"""Naive random-walk baseline, run through the same walk-forward harness
ARIMA uses, so ARIMA's real value-add (or lack of it) can be checked
against a model that does nothing but predict "no change."

Decided in 04-enhancement-of-each-angle/01-arima.md: "needed to check
ARIMA actually beats doing nothing." Reports point-forecast error
(abs_error/squared_error) directly comparable to arima_step's own fields
of the same name. Does NOT report a directional-accuracy metric: a
constant "no change" forecast has no direction of its own to be right or
wrong about, so a direction-based comparison would be comparing ARIMA
against a strawman, not a real baseline. Does NOT report a CI-coverage
"hit" either, for the same reason a constant forecast has no confidence
interval — ARIMA's own hit rate has no naive-baseline equivalent to
compare against.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.arima.backtest import MIN_OBSERVATIONS, REFIT_CADENCE
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
        refit_cadence=REFIT_CADENCE.get(timeframe, 1),  # irrelevant here (no fit to skip), kept only so step_index/is_refit_step line up 1:1 with ARIMA's own run for an apples-to-apples per-step comparison
        window=MIN_OBSERVATIONS,  # matches arima_step's rolling window -- doesn't change naive's output (it only ever reads the single latest close) but keeps step_index/bar_ts alignment exact for the comparison
        tag_fn=tag_row,
    )
