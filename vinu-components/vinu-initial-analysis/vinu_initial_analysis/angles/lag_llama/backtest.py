"""Lag-Llama's own walk-forward backtest glue code.

Group A, multi-horizon like Chronos/Kronos — a nested `predictions` dict
keyed by horizon step (1-5), each holding all 5 quantile levels the
fallback AR(5) proxy actually emits, plus hit (in [p5, p95]), per-quantile
pinball loss, and RMSE/MAE components on the p50 (median) forecast.

No weights store — the AR(5) OLS fit is a closed-form solve refit fresh
every step, not a trained model with state worth persisting (unlike the
from-scratch neural angles).
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._helpers import pinball_loss
from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.lag_llama.compute import HORIZON, MIN_OBSERVATIONS, QUANTILE_LEVELS, _fit_and_forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def lag_llama_step(step: WalkForwardStep) -> StepResult:
    closes = step.history["close"].astype(float).values
    fields = _fit_and_forecast(closes)

    quantile_forecasts = fields["quantile_forecasts"]
    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        p5 = quantile_forecasts["0.05"][h]
        p25 = quantile_forecasts["0.25"][h]
        p50 = quantile_forecasts["0.5"][h]
        p75 = quantile_forecasts["0.75"][h]
        p95 = quantile_forecasts["0.95"][h]
        predictions[str(h + 1)] = {
            "p5": p5,
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "p95": p95,
            "actual_close": actual_price,
            "hit": int(p5 <= actual_price <= p95),
            "pinball_loss": {
                "0.05": pinball_loss(0.05, p5, actual_price),
                "0.25": pinball_loss(0.25, p25, actual_price),
                "0.5": pinball_loss(0.5, p50, actual_price),
                "0.75": pinball_loss(0.75, p75, actual_price),
                "0.95": pinball_loss(0.95, p95, actual_price),
            },
            "close_sq_error": (actual_price - p50) ** 2,
            "close_abs_error": abs(actual_price - p50),
        }

    row = {
        "status": "ok",
        "model_backend": fields["model_backend"],
        "fallback_reason": fields["fallback_reason"],
        "lag_order": fields["lag_order"],
        "quantile_levels": QUANTILE_LEVELS,
        "last_close": fields["last_close"],
        "predictions": predictions,
    }
    return StepResult(row=row)


def run_lag_llama_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        lag_llama_step,
        min_observations=MIN_OBSERVATIONS,
        horizon=HORIZON,
        tag_fn=tag_row,
    )
