"""Triple-barrier labeling (08 step3, Lopez de Prado ch.3): for each start bar,
walk forward up to max_hold bars; label +1 if cumulative return first touches
+upper*vol, -1 if it first touches -lower*vol, else 0 (timeout/vertical barrier).

Pure function, no I/O. Vol defaults to rolling stdev when not given.
"""
from __future__ import annotations

import numpy as np


def triple_barrier_labels(
    close: np.ndarray,
    *,
    upper_mult: float = 1.0,
    lower_mult: float = 1.0,
    max_hold: int = 20,
    vol: np.ndarray | None = None,
    vol_window: int = 20,
) -> np.ndarray:
    close = np.asarray(close, dtype=float)
    n = len(close)
    out = np.zeros(n, dtype=int)
    if n < 2:
        return out
    rets = np.zeros(n)
    rets[1:] = close[1:] / close[:-1] - 1.0
    if vol is None:
        vol = np.array([
            float(np.std(rets[max(1, i - vol_window + 1):i + 1], ddof=1)) if i >= 1 else 0.0
            for i in range(n)
        ])
    else:
        vol = np.asarray(vol, dtype=float)
    for i in range(n - 1):
        v = float(vol[i]) if i < len(vol) else 0.0
        if v <= 0:
            continue
        upper = upper_mult * v
        lower = lower_mult * v
        cum = 0.0
        for j in range(i + 1, min(n, i + 1 + max_hold)):
            cum += float(rets[j])
            if cum >= upper:
                out[i] = 1
                break
            if cum <= -lower:
                out[i] = -1
                break
    return out
