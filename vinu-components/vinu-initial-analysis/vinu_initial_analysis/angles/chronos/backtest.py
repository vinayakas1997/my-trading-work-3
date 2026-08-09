"""Chronos's own walk-forward backtest glue code.

Third angle wired against the shared infrastructure, and the first with
a genuine multi-step (5-horizon) forecast and a nested `predictions`
storage shape -- the first real exercise of query.py's
unnest_predictions(), per 06-implementation-of-each-angles/plan.md's
build order.

No weights store is used -- nothing is trained; real pretrained weights
are loaded once (cached in-process via compute.py's _PIPELINE_CACHE) and
reused every call.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.chronos.compute import MIN_OBSERVATIONS, _forecast
from vinu_tools.compute.backtest.walk_forward import (
    StepResult,
    WalkForwardStep,
    run_walk_forward,
    run_walk_forward_parallel,
)

HORIZON = 5


def chronos_step(step: WalkForwardStep) -> StepResult:
    context = step.history["close"].astype(float).values[-MIN_OBSERVATIONS:]
    fields = _forecast(context)

    # Keys are strings, not ints -- pyarrow/parquet rejects non-str/bytes
    # dict keys ("Expected dict key of type str or bytes, got 'int'"),
    # confirmed by a real write attempt. query.py's unnest_predictions
    # casts back to int for the stored `horizon` column, so this is
    # invisible past the storage layer.
    predictions: dict[str, dict] = {}
    for h in range(HORIZON):
        actual_price = float(step.future.iloc[h]["close"])
        lower = fields["p10_forecast"][h]
        upper = fields["p90_forecast"][h]
        predictions[str(h + 1)] = {
            "p10": lower,
            "median": fields["median_forecast"][h],
            "p90": upper,
            "actual": actual_price,
            "hit": int(lower <= actual_price <= upper),
        }

    row = {
        "status": "ok",
        "model_backend": fields["model_backend"],
        "checkpoint": fields["checkpoint"],
        "last_close": fields["last_close"],
        "predictions": predictions,
    }
    return StepResult(row=row)


def run_chronos_backtest(
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
    window=MIN_OBSERVATIONS context (no per-step training/refit state to
    carry across chunks), so chunking never changes what data any step
    sees. **Not row-for-row identical to sequential, and this is not a
    parallel-wiring artifact**: Chronos's own forecast is a probabilistic
    (quantile) sample, and no fixed seed is set anywhere in this pipeline
    -- confirmed directly that even two sequential calls in the *same*
    process on identical input already produce different numbers. Unlike
    `timer_timerxl` (a genuinely deterministic point-forecaster, where
    parallel output IS provably identical), "safe" here means the
    real methodology is unchanged (same context window, same real model
    call per step), not that the numbers will match run to run -- they
    won't, with or without parallel=True. See parallel-backtest-infra.md
    for the measured scheduling numbers behind when parallel is worth
    turning on."""
    if parallel:
        return run_walk_forward_parallel(
            symbol,
            timeframe,
            bars,
            chronos_step,
            min_observations=MIN_OBSERVATIONS,
            horizon=HORIZON,
            window=MIN_OBSERVATIONS,
            tag_fn=tag_row,
            chunk_size=chunk_size,
            n_workers=n_workers,
        )
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        chronos_step,
        min_observations=MIN_OBSERVATIONS,
        horizon=HORIZON,
        window=MIN_OBSERVATIONS,  # fixed 512-candle context, not expanding -- see compute.py's MIN_OBSERVATIONS docstring
        tag_fn=tag_row,
    )
