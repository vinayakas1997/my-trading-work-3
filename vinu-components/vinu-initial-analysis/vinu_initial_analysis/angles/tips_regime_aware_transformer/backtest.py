"""tips_regime_aware_transformer's own walk-forward backtest glue code.

Group A, structurally like DLinear/lpatchtst/patchtst/tft: a fresh model
trained from scratch at every step, every step's weights saved.
Direction-match hit + RMSE/MAE, same convention as the other
trained-from-scratch angles. The one metric specific to this angle (per
04-enhancement-of-each-angle/29-tips_regime_aware_transformer.md SS3):
the already-stored `regime` field on every row lets a query group results
by momentum vs. mean_reversion directly -- no separate computation is
needed here, since compute()'s own real output already carries the
regime label per step.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.tips_regime_aware_transformer.compute import MIN_BARS, _direction, _fit_and_forecast
from vinu_initial_analysis.storage.weights import WeightsStore
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def tips_step(step: WalkForwardStep) -> StepResult:
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


def run_tips_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    data_root: str,
) -> pd.DataFrame:
    weights_store = WeightsStore(data_root)

    def _save_weights(symbol: str, timeframe: str, bar_ts: int, weights) -> str:
        return weights_store.save(symbol, "tips_regime_aware_transformer", timeframe, bar_ts, weights)

    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        tips_step,
        min_observations=MIN_BARS,
        tag_fn=tag_row,
        weights_sink=_save_weights,
    )
