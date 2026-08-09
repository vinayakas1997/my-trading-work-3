"""Chronos — Amazon's general-purpose time-series foundation model.

See ../../../New-talk-/Final-implementation/01-present-considerations/10-chronos.md
(method 10 of the 32-method plan): a T5-style transformer, pretrained on a
large cross-domain corpus of generic time series (not finance-specific),
that tokenizes a numeric context window via uniform binning and emits a
probabilistic (quantile) forecast. The spec's own caveat: general TSFMs
like Chronos often underperform finance-specific models (Kronos) on K-line
data — this angle is a zero-shot baseline/comparison point, not a
first-choice signal.

**Backend: real pretrained weights, actually used.** `chronos-forecasting`
(https://pypi.org/project/chronos-forecasting/) is a genuine, installable
Amazon package; the `amazon/chronos-t5-tiny` checkpoint (~8M params) is
pulled into the shared models dir (`vinu-infra/models.py` —
`{VINU_MODELS_DIR or data/models}/chronos-t5-tiny`, downloaded via
`make models` / `vinu-models` and mounted read-only at serve time). If the
local weights are missing they are auto-downloaded via `ensure_model`; if
the package or the fetch is unavailable at runtime (offline environment,
HF Hub unreachable), this falls back to a simple statistical proxy
(last-value-plus-drift with residual-normal quantiles) rather than failing
the whole angle — that path sets `model_backend: "fallback_proxy"` and
`fallback_reason` so callers can tell the two apart. Added to
pyproject.toml: chronos-forecasting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import get_angle_setting

ANGLE_NAME = "chronos"
# Fixed context requirement, not a growing/adaptive floor like ARIMA's
# N=100 -- 512 is Amazon's own stated ceiling *and* default for this model
# family (04-enhancement-of-each-angle/03-chronos.md SS3/SS7), so this
# angle simply requires the full 512 before evaluating rather than mixing
# an expanding-window design onto a model that always truncates to its
# last 512 candles anyway. Overridable via VINU_CHRONOS_MIN_OBSERVATIONS
# -- see ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", 512)
PREDICTION_LENGTH = 5
# Decided checkpoint (04-enhancement-of-each-angle/03-chronos.md SS3):
# upgraded from the code's prior default (chronos-t5-tiny, 8M params) to
# chronos-t5-large (710M params) for forecast quality over speed.
CHECKPOINT = "amazon/chronos-t5-large"
_MODEL_REGISTRY_NAME = "chronos-t5-large"

_PIPELINE_CACHE: dict[str, Any] = {}


def _checkpoint_path() -> str:
    """Resolve the local weights dir, auto-downloading if absent."""
    from vinu_infra.models import ensure_model

    return str(ensure_model(_MODEL_REGISTRY_NAME, quiet=True))


def _get_pipeline():
    """Lazily load and cache the Chronos pipeline across calls in-process."""
    if CHECKPOINT in _PIPELINE_CACHE:
        return _PIPELINE_CACHE[CHECKPOINT]

    import torch
    from chronos import ChronosPipeline

    pipeline = ChronosPipeline.from_pretrained(
        _checkpoint_path(), device_map="cpu", dtype=torch.float32
    )
    _PIPELINE_CACHE[CHECKPOINT] = pipeline
    return pipeline


def _fallback_forecast(closes: np.ndarray, horizon: int) -> dict[str, Any]:
    """Random-walk-with-drift + residual-normal quantiles — used only if the
    real Chronos pipeline can't be loaded (see module docstring)."""
    returns = np.diff(closes) / closes[:-1]
    drift = float(np.mean(returns))
    resid_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    last = float(closes[-1])
    steps = np.arange(1, horizon + 1)
    median = last * (1 + drift) ** steps
    spread = resid_std * np.sqrt(steps) * last
    return {
        "median_forecast": median.tolist(),
        "p10_forecast": (median - 1.2816 * spread).tolist(),
        "p90_forecast": (median + 1.2816 * spread).tolist(),
    }


def _forecast(context: np.ndarray) -> dict[str, Any]:
    """Runs one real Chronos forecast call (or the fallback proxy if the
    pipeline can't be loaded) on a context window and returns the fields
    describing it. Shared by compute() and the walk-forward backtest
    (backtest.py) so both produce the exact same forecast shape.

    Real per-call cost, benchmarked directly on this CPU-only environment
    with chronos-t5-large and a genuine 512-candle context: ~14s/call
    (pipeline load is a separate, one-time ~7s, cached across calls via
    _PIPELINE_CACHE). p10/median/p90 can be genuinely identical for a
    given horizon step when the model's 64 sampled paths concentrate onto
    one discretized value -- confirmed real and reproducible (not a code
    bug) on both chronos-t5-tiny and chronos-t5-large given a
    low-relative-volatility real context; more volatile contexts and
    later horizon steps show real nonzero spread. The natural
    `p10 <= actual <= p90` hit check handles the zero-width case
    correctly on its own (just evaluates to a near-certain miss) -- no
    special-casing needed.
    """
    model_backend = "pretrained"
    fallback_reason = None
    try:
        import torch

        pipeline = _get_pipeline()
        ctx_tensor = torch.tensor(context, dtype=torch.float32)
        samples = pipeline.predict(
            inputs=ctx_tensor, prediction_length=PREDICTION_LENGTH, num_samples=64
        )
        samples_np = samples[0].numpy()  # (num_samples, prediction_length)
        p10, median, p90 = np.quantile(samples_np, [0.1, 0.5, 0.9], axis=0)
        forecast = {
            "median_forecast": median.tolist(),
            "p10_forecast": p10.tolist(),
            "p90_forecast": p90.tolist(),
        }
    except Exception as exc:  # pragma: no cover - only hit if pkg/network unavailable
        model_backend = "fallback_proxy"
        fallback_reason = f"chronos-forecasting pipeline unavailable: {exc!r}"
        forecast = _fallback_forecast(context, PREDICTION_LENGTH)

    return {
        "model_backend": model_backend,
        "checkpoint": CHECKPOINT if model_backend == "pretrained" else None,
        "fallback_reason": fallback_reason,
        "forecast_horizon": PREDICTION_LENGTH,
        "last_close": float(context[-1]),
        **forecast,
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

    context = closes[-512:]  # Chronos context cap, per model card
    forecast_fields = _forecast(context)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(closes)),
        **forecast_fields,
    }
    return pd.DataFrame([result])
