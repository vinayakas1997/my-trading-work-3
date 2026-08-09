"""iTransformer's own walk-forward backtest glue code.

Group A, structurally like DLinear: a fresh model trained from scratch
at every walk-forward step, every step's weights saved. Unlike DLinear,
this model forecasts all 5 OHLCV channels at once -- all 5 are stored,
not just close, per the decided design.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.itransformer.compute import CHANNELS, MIN_BARS, _direction, _fit_and_forecast
from vinu_initial_analysis.storage.weights import WeightsStore
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def itransformer_step(step: WalkForwardStep) -> StepResult:
    available = [c for c in CHANNELS if c in step.history.columns]
    if "close" not in available:
        available = ["close"]
    try:
        fields, model = _fit_and_forecast(step.history, available, seed=42)
    except ValueError:
        return StepResult(row={"status": "insufficient_data", "n_observations": int(len(step.history))})

    actual_price = float(step.future.iloc[0]["close"])
    last_close = fields["last_close"]
    actual_return = (actual_price - last_close) / last_close if last_close else 0.0

    row = {
        **fields,
        "actual_price": actual_price,
        "actual_return": actual_return,
        "hit": int(fields["direction"] == _direction(actual_return)),
        # Same fields naive_baseline.py reports, for direct RMSE/MAE
        # comparison alongside the direction-hit rate.
        "abs_error": abs(actual_price - fields["forecast_price"]),
        "squared_error": (actual_price - fields["forecast_price"]) ** 2,
    }
    return StepResult(row=row, weights=model.state_dict())


def run_itransformer_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    data_root: str,
) -> pd.DataFrame:
    weights_store = WeightsStore(data_root)

    # weights_store.save() needs (symbol, angle_name, timeframe, bar_ts,
    # weights); the generic harness only ever calls weights_sink with
    # (symbol, timeframe, bar_ts, weights) -- same wrapper every
    # weight-saving angle's own glue code needs, see DLinear's backtest.py.
    def _save_weights(symbol: str, timeframe: str, bar_ts: int, weights) -> str:
        return weights_store.save(symbol, "itransformer", timeframe, bar_ts, weights)

    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        itransformer_step,
        min_observations=MIN_BARS,
        tag_fn=tag_row,
        weights_sink=_save_weights,
    )
