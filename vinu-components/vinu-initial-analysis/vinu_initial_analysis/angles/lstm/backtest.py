"""LSTM's own walk-forward backtest glue code.

Group A, structurally like DLinear: a fresh single-layer LSTM trained from
scratch at every step, every step's weights saved. Direction-match hit
(native 1-step point forecast, no confidence interval), plus RMSE/MAE
fields per the decided design (14-lstm.md) — same convention as
lpatchtst/itransformer for a point-forecast comparison against naive.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.lstm.compute import MIN_BARS, _direction, _fit_and_forecast
from vinu_initial_analysis.storage.weights import WeightsStore
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def lstm_step(step: WalkForwardStep) -> StepResult:
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
        "close_sq_error": (actual_price - fields["forecast_price"]) ** 2,
        "close_abs_error": abs(actual_price - fields["forecast_price"]),
    }
    return StepResult(row=row, weights=model.state_dict())


def run_lstm_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    data_root: str,
) -> pd.DataFrame:
    weights_store = WeightsStore(data_root)

    def _save_weights(symbol: str, timeframe: str, bar_ts: int, weights) -> str:
        return weights_store.save(symbol, "lstm", timeframe, bar_ts, weights)

    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        lstm_step,
        min_observations=MIN_BARS,
        tag_fn=tag_row,
        weights_sink=_save_weights,
    )
