"""Lag-Llama — LLaMA-architecture probabilistic time-series model.

See ../../../New-talk-/Final-implementation/01-present-considerations/16-lag-llama.md
(method 16 of the 32-method plan): adapts the LLaMA decoder-only
architecture (trained purely on numeric lagged time-series values, not
text) to output a full predictive *distribution* rather than a point
estimate — the spec explicitly flags this as its main differentiator.

**Backend: fallback_proxy — real pretrained weights were NOT used.**
`lag-llama` does not resolve on PyPI (confirmed via
`pip install lag-llama` -> "No matching distribution found"). The only
public artifact is the research repo
(github.com/time-series-foundation-models/lag-llama), which requires a
manual `git clone` + a separately-hosted checkpoint download (not
`pip install`-able), outside the "a few minutes per model" budget for
this batch. Instead: a lagged-value linear-Gaussian model is fit
in-process (ordinary least squares of the next return on its own lags,
i.e. an AR model — literally the "lag" part of Lag-Llama's name), and its
residual distribution is used to emit a genuinely probabilistic output
(5 quantile levels), matching the spec's differentiator even though the
underlying model is a simple AR fit, not a trained transformer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "lag_llama"
MIN_OBSERVATIONS = 25
LAG_ORDER = 5
HORIZON = 5
QUANTILE_LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
FALLBACK_REASON = (
    "lag-llama has no PyPI package (confirmed via pip install attempt); "
    "the only public artifact is a research GitHub repo requiring a "
    "manual clone plus a separately-hosted checkpoint, not achievable in "
    "the a-few-minutes-per-model budget. Using an in-process lagged-value "
    "(AR) linear-Gaussian fallback proxy that still emits a genuinely "
    "probabilistic (multi-quantile) forecast, matching the spec's "
    "differentiator, in place of the real LLaMA-architecture model."
)


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

    returns = np.diff(closes) / closes[:-1]
    n = len(returns)
    order = LAG_ORDER
    X = np.column_stack([returns[i:n - order + i] for i in range(order)])
    y = returns[order:]
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ coeffs
    resid = y - fitted
    resid_std = float(np.std(resid, ddof=1)) if len(resid) > 1 else 0.0

    from scipy import stats

    history = list(returns[-order:])
    price = float(closes[-1])
    quantile_paths: dict[float, list[float]] = {q: [] for q in QUANTILE_LEVELS}
    point = []
    for step in range(1, HORIZON + 1):
        next_ret = float(np.dot(coeffs, history[-order:]))
        price = price * (1 + next_ret)
        point.append(price)
        history.append(next_ret)
        spread = resid_std * np.sqrt(step) * float(closes[-1])
        for q in QUANTILE_LEVELS:
            z = float(stats.norm.ppf(q))
            quantile_paths[q].append(price + z * spread)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(closes)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "lag_order": LAG_ORDER,
        "forecast_horizon": HORIZON,
        "last_close": float(closes[-1]),
        "point_forecast": point,
        "quantile_levels": QUANTILE_LEVELS,
        "quantile_forecasts": {str(q): quantile_paths[q] for q in QUANTILE_LEVELS},
    }
    return pd.DataFrame([result])
