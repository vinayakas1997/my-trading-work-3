"""MOIRAI's own walk-forward backtest glue code.

Group A, multi-horizon like lag_llama — a nested `predictions` dict keyed
by horizon step (1-5), each holding the fallback AR(3) proxy's real
2-level band (p10/p90, not lag_llama's 5-level band — this angle's code
only ever computes these two quantile levels), hit (in [p10,p90]),
per-quantile pinball loss, and RMSE/MAE components on the point forecast.

No weights store — the AR(3) OLS fit is closed-form, refit fresh every
step, same reasoning as lag_llama.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._helpers import pinball_loss
from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.moirai.compute import HORIZON, MIN_OBSERVATIONS, _fit_and_forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def moirai_step(step: WalkForwardStep) -> StepResult:
    closes = step.history["close"].astype(float).values
    fields = _fit_and_forecast(closes)

    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        point = fields["point_forecast"][h]
        p10 = fields["p10_forecast"][h]
        p90 = fields["p90_forecast"][h]
        predictions[str(h + 1)] = {
            "point": point,
            "p10": p10,
            "p90": p90,
            "actual_close": actual_price,
            "hit": int(p10 <= actual_price <= p90),
            "pinball_loss": {
                "0.1": pinball_loss(0.1, p10, actual_price),
                "0.9": pinball_loss(0.9, p90, actual_price),
            },
            "close_sq_error": (actual_price - point) ** 2,
            "close_abs_error": abs(actual_price - point),
        }

    row = {
        "status": "ok",
        "model_backend": fields["model_backend"],
        "fallback_reason": fields["fallback_reason"],
        "any_variate_note": fields["any_variate_note"],
        "last_close": fields["last_close"],
        "predictions": predictions,
    }
    return StepResult(row=row)


def run_moirai_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        moirai_step,
        min_observations=MIN_OBSERVATIONS,
        horizon=HORIZON,
        tag_fn=tag_row,
    )
