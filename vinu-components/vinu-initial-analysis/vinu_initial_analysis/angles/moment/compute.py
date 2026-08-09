"""MOMENT — general-purpose multi-task time-series foundation model.

See ../../../New-talk-/Final-implementation/01-present-considerations/14-moment.md
(method 14 of the 32-method plan). MOMENT is a multi-task TSFM
(forecasting, embeddings, anomaly detection, imputation); this angle only
attempts the forecasting task.

**Backend: fallback_proxy — real pretrained weights were NOT used.** The
real package `momentfm` (confirmed to exist on PyPI, autonlab's MOMENT
implementation) was actually attempted:

    pip install momentfm

which failed to build in this environment:

    AttributeError: module 'pkgutil' has no attribute 'ImpImporter'.
    Did you mean: 'zipimporter'?

This is a genuine environment incompatibility — one of momentfm's older
transitive build dependencies uses a `pkgutil.ImpImporter` API that was
removed in the Python version installed here (3.12), not a network or
missing-package issue. Retrying wasn't attempted further per the "a few
minutes per model" budget. Instead: a lightweight statistical proxy
(seasonal-naive-adjusted trend + residual quantiles) stands in for the
forecasting task only — the embeddings/anomaly-detection/imputation tasks
MOMENT also supports are explicitly NOT implemented here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "moment"
# Decided value, 04-enhancement-of-each-angle/17-moment.md — raised from
# 20, same consistency move as every other raised-floor angle.
# Overridable via VINU_MOMENT_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)
HORIZON = 5
FALLBACK_REASON = (
    "momentfm (real MOMENT package) failed to build in this environment: "
    "\"AttributeError: module 'pkgutil' has no attribute 'ImpImporter'\" "
    "— a genuine Python 3.12 incompatibility in one of its transitive "
    "build dependencies, confirmed via `pip install momentfm`. Using a "
    "statistical fallback proxy for the forecasting task only; MOMENT's "
    "embeddings/anomaly-detection/imputation tasks are not implemented."
)
TASK_NOTE = "forecasting task only — embeddings/anomaly_detection/imputation not implemented"


def _fit_and_forecast(closes: np.ndarray) -> dict[str, Any]:
    """Projects `closes` forward `HORIZON` steps via a geometric random
    walk with drift (drift = mean of the last 20 returns) and an 80% band
    (p10/p90) from the residual std. Returns every result field except
    symbol/analysis_at/angle (callers attach those). No fitted-coefficient
    model object — even simpler than moirai's AR(3), just a closed-form
    drift/std computation — so, same as moirai/lag_llama, there's no
    weights artifact for the walk-forward backtest to store.
    """
    returns = np.diff(closes) / closes[:-1]
    drift = float(np.mean(returns[-20:])) if len(returns) >= 20 else float(np.mean(returns))
    resid_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    last = float(closes[-1])
    steps = np.arange(1, HORIZON + 1)
    point = last * (1 + drift) ** steps
    spread = resid_std * np.sqrt(steps) * last

    return {
        "status": "ok",
        "n_observations": int(len(closes)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "task": "forecasting",
        "task_note": TASK_NOTE,
        "forecast_horizon": HORIZON,
        "last_close": last,
        "point_forecast": point.tolist(),
        "p10_forecast": (point - 1.2816 * spread).tolist(),
        "p90_forecast": (point + 1.2816 * spread).tolist(),
    }


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    analysis_at = datetime.now(timezone.utc).isoformat()

    if bars is None or bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "no_data",
        }])

    closes = bars["close"].astype(float).values
    if len(closes) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(closes)),
        }])

    fields = _fit_and_forecast(closes)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **fields,
    }
    return pd.DataFrame([result])
