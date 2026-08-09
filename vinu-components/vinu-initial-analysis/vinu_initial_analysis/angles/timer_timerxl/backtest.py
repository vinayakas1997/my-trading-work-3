"""Timer/Timer-XL's own walk-forward backtest glue code.

Group A, multi-horizon like Chronos/Kronos -- real pretrained weights
(thuml/timer-base-84m), nested `predictions` dict keyed by horizon step
(1-5). Per the decided design (04-enhancement-of-each-angle/27-timer_timerxl.md
SS3), directional accuracy is the primary metric (the real model is a
deterministic point forecaster with no native uncertainty), CI-coverage
on the post-hoc p10/p90 band is a secondary, explicitly-caveated check
(it grades the bolted-on statistical spread, not genuine model
confidence -- same "not native" distinction as lag_llama/moirai's own
fallback proxies, except here the point forecast itself IS the real
model's output).

No weights store -- nothing is trained; real pretrained weights are
loaded once (cached in-process via compute.py's _MODEL_CACHE) and reused
every call.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.timer_timerxl.compute import MIN_OBSERVATIONS, _forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward

HORIZON = 5


def _direction(ret: float, eps: float = 1e-4) -> str:
    if ret > eps:
        return "up"
    if ret < -eps:
        return "down"
    return "flat"


def timer_timerxl_step(step: WalkForwardStep) -> StepResult:
    context = step.history["close"].astype(float).values
    fields = _forecast(context)

    last_close = fields["last_close"]
    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        point = fields["point_forecast"][h]
        p10 = fields["p10_forecast"][h]
        p90 = fields["p90_forecast"][h]
        forecast_return = (point - last_close) / last_close if last_close else 0.0
        actual_return = (actual_price - last_close) / last_close if last_close else 0.0
        predictions[str(h + 1)] = {
            "point": point,
            "p10": p10,
            "p90": p90,
            "actual": actual_price,
            "hit": int(_direction(forecast_return) == _direction(actual_return)),
            "in_band": int(p10 <= actual_price <= p90),
            "close_sq_error": (actual_price - point) ** 2,
            "close_abs_error": abs(actual_price - point),
        }

    row = {
        "status": "ok",
        "model_backend": fields["model_backend"],
        "checkpoint": fields.get("checkpoint"),
        "patch_size": fields["patch_size"],
        "n_patches": fields["n_patches"],
        "last_close": last_close,
        "predictions": predictions,
    }
    return StepResult(row=row)


def run_timer_timerxl_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        timer_timerxl_step,
        min_observations=MIN_OBSERVATIONS,
        horizon=HORIZON,
        window=MIN_OBSERVATIONS,  # fixed context, not expanding -- same reasoning as Chronos's own fixed 512-candle window
        tag_fn=tag_row,
    )
