"""Kronos's own walk-forward backtest glue code.

Group A, structurally like Chronos: real pretrained weights, a genuine
multi-step (5-horizon) forecast, nested `predictions` storage keyed by
horizon step. No weights store -- nothing is trained; real pretrained
weights are loaded once (cached in-process via compute.py's
_PREDICTOR_CACHE) and reused every call.

Dict keys are strings ("1"-"5"), not ints -- pyarrow/parquet rejects
non-str/bytes dict keys, confirmed for real during Chronos's
implementation (see 03-chronos/01-implementation.md Bug 2). Applying that
fix from the start here rather than rediscovering it.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.kronos.compute import HORIZON, MIN_OBSERVATIONS, _fit_and_forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward

# Per the decided design: 512 is the real Kronos predictor's hard context
# requirement (KronosPredictor(..., max_context=512) in compute.py), not
# a tunable floor -- same treatment as Chronos's MIN_OBSERVATIONS.
WALK_FORWARD_MIN_OBSERVATIONS = 512


def _direction(value: float, eps: float = 1e-4) -> str:
    if value > eps:
        return "up"
    if value < -eps:
        return "down"
    return "flat"


def kronos_step(step: WalkForwardStep) -> StepResult:
    ohlc_raw = step.history[["open", "high", "low", "close"]].astype(float).values
    fields = _fit_and_forecast(step.history, ohlc_raw)
    if fields["status"] != "ok" or "forecast_ohlc" not in fields:
        return StepResult(row={"status": fields.get("status", "fit_failed"), "n_observations": len(ohlc_raw)})

    last_close = fields["last_close"]
    forecast_ohlc = fields["forecast_ohlc"]

    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_close = float(step.future.iloc[h]["close"])
        forecast_close = forecast_ohlc["close"][h]
        prior_close = last_close if h == 0 else forecast_ohlc["close"][h - 1]
        predicted_direction = _direction((forecast_close - prior_close) / prior_close if prior_close else 0.0)
        prior_actual = last_close if h == 0 else float(step.future.iloc[h - 1]["close"])
        actual_direction = _direction((actual_close - prior_actual) / prior_actual if prior_actual else 0.0)
        predictions[str(h + 1)] = {
            "open": forecast_ohlc["open"][h],
            "high": forecast_ohlc["high"][h],
            "low": forecast_ohlc["low"][h],
            "close": forecast_close,
            "actual_close": actual_close,
            "predicted_direction": predicted_direction,
            "actual_direction": actual_direction,
            "hit": int(predicted_direction == actual_direction),
            "close_sq_error": (actual_close - forecast_close) ** 2,
        }

    row = {
        "status": "ok",
        "model_backend": fields["model_backend"],
        "checkpoint": fields.get("checkpoint"),
        "last_close": last_close,
        "predictions": predictions,
    }
    return StepResult(row=row)


def run_kronos_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        kronos_step,
        min_observations=WALK_FORWARD_MIN_OBSERVATIONS,
        horizon=HORIZON,
        window=WALK_FORWARD_MIN_OBSERVATIONS,  # fixed 512-candle context, not expanding
        tag_fn=tag_row,
    )
