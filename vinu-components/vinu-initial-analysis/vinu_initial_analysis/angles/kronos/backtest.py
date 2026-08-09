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
from vinu_initial_analysis.config import get_angle_setting
from vinu_tools.compute.backtest.walk_forward import (
    StepResult,
    WalkForwardStep,
    run_walk_forward,
    run_walk_forward_parallel,
)

# Per the decided design: 512 is the real Kronos predictor's hard context
# requirement (KronosPredictor(..., max_context=512) in compute.py), not
# a tunable floor -- same treatment as Chronos's MIN_OBSERVATIONS. A real,
# deliberately DIFFERENT value from compute.py's own MIN_OBSERVATIONS=30
# (that one gates the fallback-proxy path, which doesn't need the real
# model's full context) -- not a duplicate-drift bug like arima/dlinear's
# was, so this gets its own setting name rather than reusing "min_observations"
# (which would incorrectly conflate two genuinely different thresholds).
# Overridable via VINU_KRONOS_WALK_FORWARD_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
WALK_FORWARD_MIN_OBSERVATIONS = get_angle_setting("kronos", "walk_forward_min_observations", 512)


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
    *,
    parallel: bool = False,
    chunk_size: int = 200,
    n_workers: int | None = None,
) -> pd.DataFrame:
    """parallel=True dispatches to run_walk_forward_parallel instead of the
    sequential loop -- safe here because this angle uses a fixed
    window=WALK_FORWARD_MIN_OBSERVATIONS context (no per-step state to
    carry across chunks), so chunking never changes what data any step
    sees. **Not row-for-row identical to sequential, and this is not a
    parallel-wiring artifact**: confirmed directly that even two
    sequential calls in the *same* process on identical input already
    produce different numbers (the real Kronos predictor samples
    internally, same as Chronos, with no fixed seed set anywhere in this
    pipeline). Unlike `timer_timerxl` (a genuinely deterministic
    point-forecaster, where parallel output IS provably identical),
    "safe" here means the real methodology is unchanged (same context
    window, same real model call per step), not that the numbers will
    match run to run -- they won't, with or without parallel=True."""
    if parallel:
        return run_walk_forward_parallel(
            symbol,
            timeframe,
            bars,
            kronos_step,
            min_observations=WALK_FORWARD_MIN_OBSERVATIONS,
            horizon=HORIZON,
            window=WALK_FORWARD_MIN_OBSERVATIONS,
            tag_fn=tag_row,
            chunk_size=chunk_size,
            n_workers=n_workers,
        )
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
