"""TimesFM's own walk-forward backtest glue code.

Group A, multi-horizon like Chronos/Kronos/timer_timerxl -- real
pretrained weights, nested `predictions` dict keyed by horizon step
(1-5), each holding all 9 real decile levels (q10-q90, the model's own
trained quantile-head output, previously 7 of 10 discarded -- see
compute.py's module docstring). Unlike Kronos/timer_timerxl,
CI-coverage here is the PRIMARY metric, not a caveated secondary one --
per the decided design (04-enhancement-of-each-angle/28-timesfm.md SS3),
this model's quantile head is genuinely trained (`fix_quantile_crossing=True`),
so the band is real model confidence, not a bolted-on statistical
construction. Pinball loss is computed across all 9 real levels (richer
than lag_llama's 5 or moirai's 2, since this model actually outputs
that many).

No weights store -- nothing is trained; real pretrained weights are
loaded once (cached in-process via compute.py's _MODEL_CACHE) and reused
every call.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._helpers import pinball_loss
from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.timesfm.compute import DECILE_LEVELS, MAX_CONTEXT, MIN_OBSERVATIONS, _forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward

HORIZON = 5


def timesfm_step(step: WalkForwardStep) -> StepResult:
    # Expanding window (not a fixed one like Chronos's 512-candle
    # requirement) -- TimesFM's context is a quality preference, not a
    # hard per-call requirement (design doc SS3), so history is allowed
    # to grow with each step, capped at MAX_CONTEXT the same way
    # compute() itself caps it.
    context = step.history["close"].astype(float).values[-MAX_CONTEXT:]
    fields = _forecast(context)

    deciles = fields["decile_forecasts"]
    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        q10 = deciles["q10"][h]
        q90 = deciles["q90"][h]
        q50 = deciles["q50"][h]
        step_deciles = {f"q{int(q * 100)}": deciles[f"q{int(q * 100)}"][h] for q in DECILE_LEVELS}
        predictions[str(h + 1)] = {
            **step_deciles,
            "actual_close": actual_price,
            "hit": int(q10 <= actual_price <= q90),
            "pinball_loss": {
                str(q): pinball_loss(q, deciles[f"q{int(q * 100)}"][h], actual_price)
                for q in DECILE_LEVELS
            },
            "close_sq_error": (actual_price - q50) ** 2,
            "close_abs_error": abs(actual_price - q50),
        }

    row = {
        "status": "ok",
        "model_backend": fields["model_backend"],
        "checkpoint": fields.get("checkpoint"),
        "context_length_used": fields["context_length_used"],
        "last_close": fields["last_close"],
        "predictions": predictions,
    }
    return StepResult(row=row)


def run_timesfm_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        timesfm_step,
        min_observations=MIN_OBSERVATIONS,
        horizon=HORIZON,
        tag_fn=tag_row,
    )
