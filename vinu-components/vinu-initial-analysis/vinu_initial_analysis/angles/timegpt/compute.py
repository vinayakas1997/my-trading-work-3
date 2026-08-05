"""TimeGPT — Nixtla's hosted time-series forecasting API.

See ../../../New-talk-/Final-implementation/01-present-considerations/12-timegpt.md
(method 12 of the 32-method plan). The spec's own text is explicit:
"TimeGPT is typically offered as a hosted API (Nixtla) rather than an
openly-published parameter count" and model size is "Not confirmed" —
this is a **paid hosted API**, not a downloadable pretrained checkpoint.

**Backend: fallback_proxy — no real pretrained path exists to try here.**
Nixtla ships a real Python client (`nixtla`, confirmed installable via
pip), but it is only a thin wrapper that calls Nixtla's paid cloud API —
every `forecast()` call requires an `NIXTLA_API_KEY` and makes a network
request to a service this environment has no subscription/key for. There
is no self-hostable TimeGPT checkpoint to download instead (per the
spec's own caveat). Rather than fabricate a fake key or silently no-op,
this angle always runs the honestly-labeled fallback: a lightweight
statistical proxy (exponentially-weighted trend + residual-normal
quantiles), matching the point+interval output shape Nixtla's API
returns per its documented response format.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "timegpt"
MIN_OBSERVATIONS = 20
HORIZON = 5
FALLBACK_REASON = (
    "TimeGPT is a paid hosted API (Nixtla) with no self-hostable "
    "checkpoint — this environment has no NIXTLA_API_KEY / subscription, "
    "so this angle always uses a statistical fallback proxy (EWMA trend + "
    "residual-normal interval) matching the API's point+interval output "
    "shape rather than attempting a network call that would fail."
)


def _ewma_trend_forecast(closes: np.ndarray, horizon: int, span: int = 10) -> dict[str, Any]:
    series = pd.Series(closes)
    ewma = series.ewm(span=span, adjust=False).mean().values
    # drift = recent slope of the EWMA level
    recent_slope = float(ewma[-1] - ewma[-min(5, len(ewma))])
    returns = np.diff(closes) / closes[:-1]
    resid_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    last = float(closes[-1])
    steps = np.arange(1, horizon + 1)
    point = last + recent_slope * steps / max(min(5, len(ewma)), 1)
    spread = resid_std * np.sqrt(steps) * last
    return {
        "point_forecast": point.tolist(),
        "lo_80_forecast": (point - 1.2816 * spread).tolist(),
        "hi_80_forecast": (point + 1.2816 * spread).tolist(),
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

    has_api_key = bool(os.environ.get("NIXTLA_API_KEY"))
    forecast = _ewma_trend_forecast(closes, HORIZON)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(closes)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "api_key_configured": has_api_key,
        "forecast_horizon": HORIZON,
        "last_close": float(closes[-1]),
        **forecast,
    }
    return pd.DataFrame([result])
