"""garch's own walk-forward backtest glue code.

Not a price/direction forecaster -- forecasts volatility (magnitude),
evaluated with QLIKE (the standard metric in volatility-forecasting
research), not a hit/miss. No weights store: nothing is trained in the
neural-net sense. No naive-baseline comparison: not part of the decided
design for this angle (unlike ARIMA/Chronos/exponential_smoothing),
so none is added here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.garch.compute import MIN_OBSERVATIONS, _fit_and_forecast
from vinu_tools.compute.backtest.walk_forward import StepResult, WalkForwardStep, run_walk_forward


def _qlike(realized_var: float, forecast_var: float) -> float:
    """QLIKE loss: realized/forecast - ln(realized/forecast) - 1 (Patton
    2011) -- the standard continuous evaluation metric for a variance
    forecast; zero at a perfect forecast, always >= 0 otherwise."""
    ratio = max(realized_var, 1e-12) / max(forecast_var, 1e-12)
    return float(ratio - np.log(ratio) - 1)


def _vol_direction(current_vol: float, prior_vol: float, eps: float = 1e-9) -> str:
    if current_vol > prior_vol + eps:
        return "rising"
    if current_vol < prior_vol - eps:
        return "falling"
    return "flat"


def _garch_step(step: WalkForwardStep, timeframe: str) -> StepResult:
    """Real step logic, factored out so it can be unit-tested directly
    without needing a full run_walk_forward call. `timeframe` is required
    (garch_volatility's annualization factor depends on it) but
    WalkForwardStep doesn't carry it, hence the thin closure in
    run_garch_backtest below.
    """
    close = step.history["close"].astype(float).values
    returns = pd.Series(close).pct_change().dropna().values
    try:
        fields = _fit_and_forecast(returns, timeframe)
    except Exception:
        return StepResult(row={"status": "fit_failed", "n_observations": int(len(returns))})

    actual_price = float(step.future.iloc[0]["close"])
    last_close = close[-1]
    actual_next_return = (actual_price - last_close) / last_close if last_close else 0.0
    realized_variance = actual_next_return ** 2
    forecast_variance = fields["next_period_variance_forecast"]
    qlike_error = _qlike(realized_variance, forecast_variance)

    # Prior period's realized volatility (abs of the last known return) is
    # the reference point for "did the forecast correctly call rising vs
    # falling" -- the model's own last input, not a look-ahead value.
    prior_realized_vol = abs(float(returns[-1])) if len(returns) else 0.0
    forecasted_vol_direction = _vol_direction(fields["next_period_volatility_forecast"], prior_realized_vol)
    actual_vol_direction = _vol_direction(abs(actual_next_return), prior_realized_vol)

    row = {
        **fields,
        "actual_next_return": actual_next_return,
        "realized_variance": realized_variance,
        "qlike_error": qlike_error,
        "forecasted_vol_direction": forecasted_vol_direction,
        "actual_vol_direction": actual_vol_direction,
        "vol_direction_hit": int(forecasted_vol_direction == actual_vol_direction),
    }
    return StepResult(row=row)


def run_garch_backtest(
    symbol: str,
    timeframe: str,
    bars: pd.DataFrame,
) -> pd.DataFrame:
    def step_fn(step: WalkForwardStep) -> StepResult:
        return _garch_step(step, timeframe)

    return run_walk_forward(
        symbol,
        timeframe,
        bars,
        step_fn,
        min_observations=MIN_OBSERVATIONS,
        refit_cadence=1,  # real benchmark: fit is cheap (~0.027s), no cadence trick needed
        window=MIN_OBSERVATIONS,
        tag_fn=tag_row,
    )
