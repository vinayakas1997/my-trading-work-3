"""TimesFM — Google's general-purpose time-series foundation model.

See ../../../New-talk-/Final-implementation/01-present-considerations/11-timesfm.md
(method 11 of the 32-method plan): a decoder-only transformer pretrained
on a large, diverse (not finance-specific) time-series corpus, used
zero-shot for point + quantile forecasting. Same family caveat as Chronos
(10-chronos.md): general TSFMs tend to underperform finance-specific
models on K-line data — treat this as a zero-shot comparison baseline.

**Backend: real pretrained weights, actually used.** `timesfm[torch]`
(https://pypi.org/project/timesfm/) is Google's genuine, installable
package; the `google/timesfm-2.5-200m-pytorch` checkpoint (200M params,
~800MB) lives in the shared models dir (`vinu-infra/models.py` —
`{VINU_MODELS_DIR or data/models}/timesfm-2.5-200m-pytorch`, downloaded via
`make models` / `vinu-models` and mounted read-only at serve time). If the
local weights are missing they are auto-downloaded via `ensure_model`;
confirmed the torch backend needs no jax/flax, so this does not touch the
already-installed torch 2.13 build. If the package/network fetch is
unavailable at runtime, this falls back to a simple statistical proxy
(linear-trend extrapolation with residual-normal quantiles), labeled
`model_backend: "fallback_proxy"`. Added to pyproject.toml: timesfm[torch].
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "timesfm"
# Decided value, 04-enhancement-of-each-angle/28-timesfm.md — raised from
# 30, same consistency move as every other angle (a quality floor here,
# not an architectural requirement the way Kronos's context length is).
MIN_OBSERVATIONS = 100
HORIZON = 5
# Decided value — raised from 256, matching the model's own documented
# default operating configuration (HuggingFace card default config uses
# max_context=1024) rather than running it at a quarter of its normal
# context.
MAX_CONTEXT = 1024
CHECKPOINT = "google/timesfm-2.5-200m-pytorch"
DECILE_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

_MODEL_CACHE: dict[str, Any] = {}


def _checkpoint_path() -> str:
    """Resolve the local weights dir, auto-downloading if absent."""
    from vinu_infra.models import ensure_model

    return str(ensure_model("timesfm-2.5-200m-pytorch", quiet=True))


def _get_model():
    if CHECKPOINT in _MODEL_CACHE:
        return _MODEL_CACHE[CHECKPOINT]

    import timesfm

    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(_checkpoint_path())
    model.compile(
        timesfm.ForecastConfig(
            max_context=MAX_CONTEXT,
            max_horizon=HORIZON,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
            force_flip_invariance=True,
            infer_is_positive=True,
            fix_quantile_crossing=True,
        )
    )
    _MODEL_CACHE[CHECKPOINT] = model
    return model


def _fallback_forecast(closes: np.ndarray, horizon: int) -> dict[str, Any]:
    """Linear-trend extrapolation + residual-normal quantiles — used only
    if the real TimesFM checkpoint can't be loaded (see module docstring).
    Emits all 9 decile levels (from the same Gaussian spread) so the
    fallback path's output shape matches the real model's, even though
    the real model's deciles are genuine trained output and these are a
    statistical construction.
    """
    from scipy import stats

    x = np.arange(len(closes))
    slope, intercept = np.polyfit(x, closes, 1)
    resid = closes - (slope * x + intercept)
    resid_std = float(np.std(resid, ddof=1)) if len(resid) > 1 else 0.0
    future_x = np.arange(len(closes), len(closes) + horizon)
    point = slope * future_x + intercept
    spread = resid_std * np.sqrt(np.arange(1, horizon + 1))
    deciles = {}
    for q in DECILE_LEVELS:
        z = float(stats.norm.ppf(q))
        deciles[f"q{int(q * 100)}"] = (point + z * spread).tolist()
    return {
        "point_forecast": point.tolist(),
        "decile_forecasts": deciles,
    }


def _forecast(context: np.ndarray) -> dict[str, Any]:
    """Runs one real TimesFM forecast call (or the fallback proxy if the
    checkpoint can't be loaded) and returns the fields describing it.
    Shared by compute() and the walk-forward backtest (backtest.py) so
    both produce the exact same forecast shape.
    """
    model_backend = "pretrained"
    fallback_reason = None

    try:
        model = _get_model()
        point_fc, quantile_fc = model.forecast(horizon=HORIZON, inputs=[context])
        point = np.asarray(point_fc[0])
        # quantile_fc returns [mean, q10, q20, ..., q90] per step (index 0
        # is the mean, indices 1-9 are the 9 real decile levels) -- all 9
        # kept, not just q10/q90 (previously discarded, see module
        # docstring: "7 of the 10 real quantile levels... thrown away").
        deciles = {
            f"q{int(q * 100)}": np.asarray(quantile_fc[0, :, i + 1]).tolist()
            for i, q in enumerate(DECILE_LEVELS)
        }
        forecast = {
            "point_forecast": point.tolist(),
            "decile_forecasts": deciles,
        }
    except Exception as exc:  # pragma: no cover - only hit if pkg/network unavailable
        model_backend = "fallback_proxy"
        fallback_reason = f"timesfm pretrained checkpoint unavailable: {exc!r}"
        forecast = _fallback_forecast(context, HORIZON)

    return {
        "status": "ok",
        "n_observations": int(len(context)),
        "model_backend": model_backend,
        "checkpoint": CHECKPOINT if model_backend == "pretrained" else None,
        "fallback_reason": fallback_reason,
        "context_length_used": int(len(context)),
        "forecast_horizon": HORIZON,
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

    context = closes[-MAX_CONTEXT:]
    fields = _forecast(context)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **fields,
    }
    return pd.DataFrame([result])
