"""Timer / Timer-XL — patch-based time-series foundation models.

See ../../../New-talk-/Final-implementation/01-present-considerations/15-timer-timerxl.md
(method 15 of the 32-method plan): a window of the series is split into
fixed-size patches (patch length 96), and a next-patch autoregressive
transformer (THUML's Timer, 84M params, pretrained on 260B time points)
forecasts forward. Timer-XL is the long-context variant of Timer; the
downloaded checkpoint `thuml/timer-base-84m` is the base Timer.

**Backend: real pretrained weights, actually used.** The checkpoint is
pulled into the shared models dir (`vinu-infra/models.py` —
`{VINU_MODELS_DIR or data/models}/timer-timerxl`, downloaded via
`make models` / `vinu-models` and mounted read-only at serve time). If the
local weights are missing they are auto-downloaded via `ensure_model`; if
the fetch or transformers' remote-code load is unavailable at runtime, this
falls back to a statistical proxy (per-patch mean log-return trend
extrapolation) rather than failing the whole angle — that path sets
`model_backend: "fallback_proxy"` and `fallback_reason` so callers can tell
the two apart.

Notes on usage:
- The model is a deterministic *point* forecaster, so the p10/p90 bands are
  derived from the residual std of log-returns (same spread construction as
  the proxy) centered on the model's point forecast.
- Inference uses a single `forward` pass (`use_cache=False`) instead of
  `generate()` because the vendored `TSGenerationMixin` (written for
  transformers 4.40.x) calls removed transformers 5.x APIs
  (`DynamicCache.from_legacy_cache`, `DynamicCache.seen_tokens`).
- Input is log-transformed (model pretrained on generic normalized series;
  revin re-standardizes) and truncated to a multiple of the 96-point patch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "timer_timerxl"
# Decided value, 04-enhancement-of-each-angle/27-timer_timerxl.md — raised
# from 24. Not just cross-angle consistency: below PATCH_SIZE=96, the real
# model can never produce even one patch and silently falls through to the
# fallback proxy every time (a real behavioral quirk, not just a floor
# bump) -- 100 clears that real architectural requirement.
MIN_OBSERVATIONS = 100
PATCH_SIZE = 96
MAX_CONTEXT = 2880
HORIZON = 5
FALLBACK_REASON = (
    "Timer pretrained weights unavailable at runtime (missing download or "
    "transformers remote-code load failed); using the patch-based "
    "statistical proxy (per-patch mean log-return trend extrapolation) "
    "instead of the real pretrained transformer."
)

_MODEL_CACHE: dict[str, Any] = {}


def _checkpoint_path() -> str:
    """Resolve the local weights dir, auto-downloading if absent."""
    from vinu_infra.models import ensure_model

    return str(ensure_model("timer-timerxl", quiet=True))


def _get_model():
    """Lazily load and cache the TimerForPrediction model in-process."""
    if ANGLE_NAME in _MODEL_CACHE:
        return _MODEL_CACHE[ANGLE_NAME]

    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(
        _checkpoint_path(), trust_remote_code=True
    )
    model.eval()
    _MODEL_CACHE[ANGLE_NAME] = model
    return model


def _fallback_forecast(closes: np.ndarray) -> dict[str, Any]:
    """Patch-mean log-return trend extrapolation — used only if the real
    Timer model can't be loaded (see module docstring)."""
    log_returns = np.diff(np.log(np.clip(closes, 1e-8, None)))
    n_patches = len(log_returns) // PATCH_SIZE
    if n_patches < 1:
        next_patch_mean_ret = float(np.mean(log_returns)) if len(log_returns) else 0.0
        resid_std = (
            float(np.std(log_returns, ddof=1)) if len(log_returns) > 1 else 0.0
        )
    else:
        usable = n_patches * PATCH_SIZE
        patches = log_returns[-usable:].reshape(n_patches, PATCH_SIZE)
        patch_means = patches.mean(axis=1)
        patch_idx = np.arange(n_patches)
        if n_patches >= 2:
            slope, intercept = np.polyfit(patch_idx, patch_means, 1)
        else:
            slope, intercept = 0.0, float(patch_means[-1])
        next_patch_mean_ret = float(slope * n_patches + intercept)
        resid_std = float(np.std(patch_means, ddof=1)) if n_patches > 1 else 0.0
    last = float(closes[-1])
    steps = np.arange(1, HORIZON + 1)
    point = last * np.exp(next_patch_mean_ret * steps)
    spread = resid_std * np.sqrt(steps) * last
    return {
        "point_forecast": point.tolist(),
        "p10_forecast": (point - 1.2816 * spread).tolist(),
        "p90_forecast": (point + 1.2816 * spread).tolist(),
    }


def _quantile_bands(
    point: np.ndarray, closes: np.ndarray, last: float
) -> tuple[list[float], list[float]]:
    """Residual-normal quantile bands around the model's point forecast."""
    returns = np.diff(np.log(np.clip(closes, 1e-8, None)))
    resid_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    steps = np.arange(1, HORIZON + 1)
    spread = resid_std * np.sqrt(steps) * last
    return (point - 1.2816 * spread).tolist(), (point + 1.2816 * spread).tolist()


def _forecast(closes: np.ndarray) -> dict[str, Any]:
    """Runs one real Timer forecast call (or the fallback proxy if the
    pipeline can't be loaded) and returns the fields describing it.
    Shared by compute() and the walk-forward backtest (backtest.py) so
    both produce the exact same forecast shape.
    """
    model_backend = "pretrained"
    fallback_reason = None
    n_patches = 0

    try:
        import torch

        model = _get_model()
        context = closes[-MAX_CONTEXT:]
        usable = (len(context) // PATCH_SIZE) * PATCH_SIZE
        context = context[-usable:]
        n_patches = len(context) // PATCH_SIZE
        if n_patches < 1:
            raise ValueError(
                f"need >= {PATCH_SIZE} points for one Timer patch; got {len(context)}"
            )

        seq = torch.tensor(
            np.log(np.clip(context, 1e-8, None)), dtype=torch.float32
        ).unsqueeze(0)
        with torch.no_grad():
            out = model(input_ids=seq, max_output_length=HORIZON, revin=True, use_cache=False)
        point = np.exp(out.logits[0].numpy())  # (HORIZON,)
        last = float(closes[-1])
        p10, p90 = _quantile_bands(point, closes, last)
        return {
            "status": "ok",
            "n_observations": int(len(closes)),
            "model_backend": model_backend,
            "checkpoint": "thuml/timer-base-84m",
            "fallback_reason": fallback_reason,
            "patch_size": PATCH_SIZE,
            "n_patches": int(n_patches),
            "forecast_horizon": HORIZON,
            "last_close": last,
            "point_forecast": point.tolist(),
            "p10_forecast": p10,
            "p90_forecast": p90,
        }
    except Exception as exc:  # pragma: no cover - only hit if pkg/network unavailable
        forecast = _fallback_forecast(closes)
        return {
            "status": "ok",
            "n_observations": int(len(closes)),
            "model_backend": "fallback_proxy",
            "fallback_reason": f"{FALLBACK_REASON} Detail: {exc!r}",
            "patch_size": PATCH_SIZE,
            "n_patches": int(len(closes) // PATCH_SIZE),
            "forecast_horizon": HORIZON,
            "last_close": float(closes[-1]),
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

    fields = _forecast(closes)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **fields,
    }
    return pd.DataFrame([result])
