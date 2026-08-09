"""DLinear's own walk-forward backtest glue code.

DLinear is the first angle wired against the shared infrastructure (see
05-storage-enhancement-levels/plan.md) because its design touches all four
shared pieces: tagging, the walk-forward loop, the weights store (a fresh
model is trained at every step), and query-layer aggregation.

Everything DLinear-specific (training, forecasting, what counts as a hit)
lives in `dlinear_step`. Everything generic (window sliding, tagging every
row the same way, saving weights the same way) comes from the shared
pieces — nothing generic lives in this file.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.dlinear.compute import (
    _direction,
    _fit_and_forecast,
    MIN_BARS as MIN_OBSERVATIONS,
)
from vinu_initial_analysis.storage.weights import WeightsStore
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward

# Was its own hardcoded duplicate of compute.py's MIN_BARS (both happened
# to be 100, but nothing kept them in sync) -- now imported directly so
# there's one real value, and VINU_DLINEAR_MIN_OBSERVATIONS (see
# compute.py) covers both call sites automatically.


def dlinear_step(step: WalkForwardStep) -> StepResult:
    close = step.history["close"].astype(float).values
    try:
        fields, model = _fit_and_forecast(close, seed=42)
    except ValueError:
        return StepResult(row={"status": "insufficient_data", "n_observations": int(len(close))})

    actual_price = float(step.future.iloc[0]["close"])
    last_close = fields["last_close"]
    actual_return = (actual_price - last_close) / last_close if last_close else 0.0

    row = {
        **fields,
        "actual_price": actual_price,
        "actual_return": actual_return,
        "hit": int(fields["direction"] == _direction(actual_return)),
    }
    return StepResult(row=row, weights=model.state_dict())


def run_dlinear_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    data_root: str,
) -> pd.DataFrame:
    weights_store = WeightsStore(data_root)

    # weights_store.save() needs (symbol, angle_name, timeframe, bar_ts,
    # weights), but the generic harness only ever calls weights_sink with
    # (symbol, timeframe, bar_ts, weights) — it has no concept of
    # "angle_name". This is DLinear's job to close over.
    def _save_weights(symbol: str, timeframe: str, bar_ts: int, weights) -> str:
        return weights_store.save(symbol, "dlinear", timeframe, bar_ts, weights)

    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        dlinear_step,
        min_observations=MIN_OBSERVATIONS,
        tag_fn=tag_row,
        weights_sink=_save_weights,
    )
