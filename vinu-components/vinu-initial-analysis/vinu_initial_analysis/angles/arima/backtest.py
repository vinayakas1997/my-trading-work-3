"""ARIMA's own walk-forward backtest glue code.

Second angle wired against the shared infrastructure, and the first to
need two things DLinear didn't:

1. A CI-coverage hit definition (actual close falls inside ARIMA's own
   95% confidence interval) instead of a direction-match.
2. A non-trivial refit cadence for the two finest timeframes (1min, 5min)
   — re-running the full AIC grid search every single step is real-fitted-
   and-measured too slow at that resolution (benchmarked: ~0.53s per
   17-order grid-search fit on a real 100-candle window vs. ~0.003s for an
   `.append(refit=False)` extension of an already-fitted model — about
   170x cheaper). `state`/`prior_state` exist in the shared harness
   specifically for this: on a non-refit step, extend the previous step's
   fitted results object instead of re-fitting from scratch.

No weights store is used here — ARIMA isn't one of the trained-from-scratch
neural-net angles (DLinear/LSTM/LPatchTST/PatchTST/TFT/iTransformer/TIPS)
the weights store was built for; `StepResult.weights` is always None.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.arima.compute import (
    _fit_and_forecast,
    _forecast_fields,
    _MIN_OBSERVATIONS as MIN_OBSERVATIONS,
)
from vinu_tools.compute.backtest.walk_forward import (
    StepResult,
    WalkForwardStep,
    run_walk_forward,
    run_walk_forward_parallel,
)

# Was its own hardcoded duplicate of compute.py's _MIN_OBSERVATIONS (both
# happened to be 100, but nothing kept them in sync) -- now imported
# directly so there's one real value, and VINU_ARIMA_MIN_OBSERVATIONS
# (see compute.py) covers both call sites automatically.

# Refit cadence per timeframe. 1H/4H/1D refit every step (design doc's
# explicit decision — few enough bars over any real window that a full
# grid-search refit every step is cheap). 1min/5min refit every N steps
# (design doc's explicit decision, N chosen below from a real benchmark,
# not the doc's own flagged-as-unverified guess). 15min has no named
# constant in the design doc (only N_1MIN/N_5MIN/N_1H/N_4H/N_1D are
# named) -- extending the same "refit about once per hour of market time"
# rule used for 1min/5min to 15min as the natural, principled way to fill
# that gap, not a re-derivation from scratch.
REFIT_CADENCE = {
    "1min": 60,   # ~once per hour of market time
    "5min": 12,   # ~once per hour of market time
    "15min": 4,   # ~once per hour of market time
    "1H": 1,
    "4H": 1,
    "1D": 1,
}


def arima_step(step: WalkForwardStep) -> StepResult:
    close = step.history["close"].astype(float).values

    if step.is_refit_step or step.prior_state is None:
        try:
            fields, res = _fit_and_forecast(close)
        except ValueError:
            return StepResult(row={"status": "fit_failed", "n_observations": int(len(close))})
    else:
        prior_res, prior_order = step.prior_state
        new_obs = float(close[-1])
        res = prior_res.append([new_obs], refit=False)
        fields = _forecast_fields(res, prior_order, len(close))

    order = (fields["order"]["p"], fields["order"]["d"], fields["order"]["q"])

    actual_price = float(step.future.iloc[0]["close"])
    lower, upper = fields["confidence_interval"]
    hit = int(lower <= actual_price <= upper)

    row = {
        **fields,
        "actual_price": actual_price,
        "hit": hit,
        # Point-forecast error magnitude, same fields naive_baseline.py
        # reports, so the two are directly comparable on RMSE/MAE --
        # "hit" (CI-coverage) has no naive-baseline equivalent (a constant
        # forecast has no confidence interval), so that comparison only
        # ever happens on these two fields, not on hit.
        "abs_error": abs(actual_price - fields["forecast"]),
        "squared_error": (actual_price - fields["forecast"]) ** 2,
    }
    return StepResult(row=row, state=(res, order))


def run_arima_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
    data_root: str,
    *,
    parallel: bool = False,
    chunk_size: int = 200,
    n_workers: int | None = None,
) -> pd.DataFrame:
    """parallel=True dispatches to run_walk_forward_parallel instead of the
    sequential loop. **Caveat specific to this angle**:
    run_walk_forward_parallel does not support refit_cadence/prior_state
    chaining at all -- every step runs as a fresh, independent fit
    (is_refit_step=True, prior_state=None always). For 1H/4H/1D
    (REFIT_CADENCE == 1, already refits every step sequentially too),
    parallel output is row-for-row identical to sequential -- a pure
    scheduling change. For 1min/5min/15min (REFIT_CADENCE > 1), this is
    NOT row-for-row identical: sequential mode only fully refits every
    Nth step and cheaply extends the fit in between
    (`.append(refit=False)`, ~170x cheaper, see module docstring); parallel
    mode fully re-runs the AIC grid search on every single step instead,
    which is both a real behavior change (a fresh fit can choose a
    different (p,d,q) order than an extended one) and, for these
    timeframes specifically, likely *slower* overall despite the process
    pool -- it does strictly more full fits than sequential does, not
    just the same fits rescheduled. Turning parallel=True on for
    1min/5min/15min is a real, deliberate trade (more/costlier real fits
    per run) not a free win the way it is for the other 6 angles; safe
    and identical only for 1H/4H/1D.
    """
    refit_cadence = REFIT_CADENCE.get(timeframe, 1)
    if parallel:
        return run_walk_forward_parallel(
            symbol,
            timeframe,
            bars,
            arima_step,
            min_observations=MIN_OBSERVATIONS,
            window=MIN_OBSERVATIONS,
            tag_fn=tag_row,
            chunk_size=chunk_size,
            n_workers=n_workers,
        )
    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        arima_step,
        min_observations=MIN_OBSERVATIONS,
        refit_cadence=refit_cadence,
        # Fixed-size rolling window, not the harness's "expanding" default --
        # the decided design (04-enhancement-of-each-angle/01-arima.md) says
        # "rolling refit", and an expanding window also means every fit's
        # cost keeps growing through the backtest (confirmed for real: 1H
        # took 1051s with an expanding window because late steps were
        # fitting on 900+ candles, not the ~0.5s/fit benchmarked on a
        # 100-candle window). A fixed 100-candle window keeps fit cost flat.
        window=MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )
