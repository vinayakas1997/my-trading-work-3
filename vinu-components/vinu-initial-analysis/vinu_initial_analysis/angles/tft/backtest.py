"""TFT's own walk-forward backtest glue code.

Group A, structurally like DLinear/lpatchtst/patchtst: a fresh model
trained from scratch at every step, every step's weights saved. Unlike
those point-forecast angles, this one's real output is a genuine
non-crossing P10/P50/P90 quantile triple (guaranteed by construction, see
compute.py's module docstring) -- so this backtest reports both
CI-coverage (actual in [P10,P90]) and directional accuracy on P50, plus
pinball loss (reusing the shared `pinball_loss`) and RMSE/MAE on P50,
per the decided design (04-enhancement-of-each-angle/26-tft.md SS3).
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._helpers import pinball_loss
from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.tft.compute import MIN_BARS, QUANTILES, _fit_and_forecast
from vinu_initial_analysis.storage.weights import WeightsStore
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def _direction(ret: float, eps: float = 1e-4) -> str:
    if ret > eps:
        return "up"
    if ret < -eps:
        return "down"
    return "flat"


def tft_step(step: WalkForwardStep) -> StepResult:
    try:
        fields, model = _fit_and_forecast(step.history, seed=42)
    except ValueError:
        return StepResult(row={"status": "insufficient_data", "n_observations": int(len(step.history))})

    actual_price = float(step.future.iloc[0]["close"])
    last_close = fields["last_close"]
    actual_return = (actual_price - last_close) / last_close if last_close else 0.0
    p10, p50, p90 = fields["forecast_price_p10"], fields["forecast_price_p50"], fields["forecast_price_p90"]

    row = {
        **fields,
        "actual_price": actual_price,
        "actual_return": actual_return,
        "hit": int(fields["direction"] == _direction(actual_return)),
        "in_band": int(p10 <= actual_price <= p90),
        "pinball_loss": {
            "0.1": pinball_loss(QUANTILES[0], p10, actual_price),
            "0.5": pinball_loss(QUANTILES[1], p50, actual_price),
            "0.9": pinball_loss(QUANTILES[2], p90, actual_price),
        },
        "close_sq_error": (actual_price - p50) ** 2,
        "close_abs_error": abs(actual_price - p50),
    }
    return StepResult(row=row, weights=model.state_dict())


def run_tft_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    data_root: str,
) -> pd.DataFrame:
    weights_store = WeightsStore(data_root)

    def _save_weights(symbol: str, timeframe: str, bar_ts: int, weights) -> str:
        return weights_store.save(symbol, "tft", timeframe, bar_ts, weights)

    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        tft_step,
        min_observations=MIN_BARS,
        tag_fn=tag_row,
        weights_sink=_save_weights,
    )
