"""PatchFormer — general-purpose patch-based time-series foundation model.

See ../../../New-talk-/Final-implementation/01-present-considerations/17-patchformer.md
(method 17 of the 32-method plan). The spec is explicit that this file is
thinner than its siblings: architecture, exact input pattern, and output
shape are all "not confirmed in this research pass" beyond a bare arXiv
citation (arXiv:2601.20845) and being grouped with the rest of the TSFM
family.

**Backend: fallback_proxy — real pretrained weights were NOT used.**
`patchformer` does not resolve on PyPI (confirmed via
`pip install patchformer` -> "No matching distribution found"), and no
GitHub repo/checkpoint was tracked down for it either (the spec's own
"Fit with existing project structure" section flags this as unconfirmed,
not just untried). Given the spec itself couldn't confirm the real
model's shape, this angle implements the one concrete thing the spec does
confirm — patch-based windowing of a single series — as a statistical
proxy: overlapping patches are embedded as simple (mean, std) summary
vectors, and a k-nearest-neighbor lookup over the ticker's own historical
patches picks the most similar prior patch's subsequent move as the
forecast (a patch-similarity forecast, not a trained transformer).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "patchformer"
MIN_OBSERVATIONS = 40
PATCH_SIZE = 8
HORIZON = 5
FALLBACK_REASON = (
    "patchformer has no PyPI package (confirmed via pip install attempt), "
    "and the spec itself (17-patchformer.md) could not confirm the real "
    "model's architecture/input/output shape beyond a bare arXiv citation "
    "— no pretrained path exists to try. Using a patch-similarity "
    "(k-NN over historical (mean, std) patch summaries) statistical proxy "
    "instead of the real pretrained transformer."
)


def _make_patches(log_returns: np.ndarray, patch_size: int) -> np.ndarray:
    n_patches = len(log_returns) // patch_size
    usable = n_patches * patch_size
    return log_returns[-usable:].reshape(n_patches, patch_size)


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

    log_returns = np.diff(np.log(np.clip(closes, 1e-8, None)))
    patches = _make_patches(log_returns, PATCH_SIZE)
    n_patches = len(patches)

    if n_patches < 3:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(closes)),
        }])

    summaries = np.column_stack([patches.mean(axis=1), patches.std(axis=1)])
    query = summaries[-1]
    # exclude the query patch itself from the neighbor search
    candidates = summaries[:-1]
    dists = np.linalg.norm(candidates - query, axis=1)
    k = min(3, len(candidates))
    nn_idx = np.argsort(dists)[:k]

    # forecast = average subsequent-patch mean return of the k nearest
    # historical patches (falls back to the query patch's own mean if a
    # neighbor is the very last patch with no successor)
    next_patch_rets = []
    for idx in nn_idx:
        if idx + 1 < len(patches):
            next_patch_rets.append(float(patches[idx + 1].mean()))
    predicted_patch_mean_ret = float(np.mean(next_patch_rets)) if next_patch_rets else float(query[0])

    resid_std = float(np.std(summaries[:, 0], ddof=1)) if n_patches > 1 else 0.0
    last = float(closes[-1])
    steps = np.arange(1, HORIZON + 1)
    point = last * np.exp(predicted_patch_mean_ret * steps)
    spread = resid_std * np.sqrt(steps) * last

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(closes)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "patch_size": PATCH_SIZE,
        "n_patches": int(n_patches),
        "nearest_neighbor_patches": int(k),
        "forecast_horizon": HORIZON,
        "last_close": last,
        "point_forecast": point.tolist(),
        "p10_forecast": (point - 1.2816 * spread).tolist(),
        "p90_forecast": (point + 1.2816 * spread).tolist(),
    }
    return pd.DataFrame([result])
