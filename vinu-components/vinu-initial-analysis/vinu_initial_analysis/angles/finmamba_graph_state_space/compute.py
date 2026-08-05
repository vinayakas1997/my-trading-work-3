"""FinMamba — graph-enhanced Mamba (state-space model) for stock movement.

See ../../../New-talk-/Final-implementation/01-present-considerations/
31-finmamba-graph-state-space.md (method 31): a Mamba/SSM backbone (linear-
time sequence modeling instead of attention) plus a market-aware graph
layer across stocks, predicting stock movement (up/down or magnitude)
from a 20-step price window.

**Backend: fallback_proxy — no install attempt was made, by design.**
The spec's own "Model size / base model" section is explicit: "No total
parameter count disclosed in the accessible sections ... referenced as
living in the paper's appendix (Sec. A.4), which wasn't captured in this
extraction" — public availability/size is unconfirmed, and no PyPI
package or repo reference is given at all (only two arXiv links). Per
this batch's instruction to implement the fallback-proxy path directly in
that case rather than hunting for a nonexistent package, no `pip install`
attempt was made. Instead: a minimal linear state-space recursion
(h_t = a*h_{t-1} + b*x_t, i.e. the simplest possible single-channel SSM —
structurally the same "process sequences with a recurrent linear-time
state" idea Mamba generalizes, at a scale this can actually run) produces
a hidden state used for an up/down movement classification. The spec's
market-aware graph layer needs multiple stocks jointly, and (same as the
cross-attention-GCN and MOIRAI angles in this batch) this angle's
`compute()` is called per single symbol — so the graph layer is likewise
structurally degenerate here (single-node, no cross-stock edges),
explicitly noted in the output rather than silently assumed away.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "finmamba_graph_state_space"
MIN_OBSERVATIONS = 25
WINDOW = 20  # spec: "a 20-step historical price window"
FALLBACK_REASON = (
    "FinMamba's spec (31-finmamba-graph-state-space.md) discloses no "
    "total parameter count and gives no PyPI package or installable repo "
    "reference (only arXiv links) — public availability is unconfirmed. "
    "Per this batch's instruction to skip hunting for a nonexistent "
    "package in that case, using a minimal single-channel linear "
    "state-space recursion (h_t = a*h_{t-1} + b*x_t) as an SSM-in-spirit "
    "proxy, not the real Mamba backbone."
)
GRAPH_NOTE = (
    "The spec's market-aware graph layer needs multiple stocks jointly; "
    "compute() here is called for a single symbol at a time, so the graph "
    "layer is a single-node graph (no cross-stock edges), not the real "
    "multi-stock structure."
)


def _fit_linear_ssm(returns: np.ndarray) -> tuple[float, float]:
    """Fits h_t = a*h_{t-1} + b*x_t by treating h_t == returns[t] (a
    first-order linear recursion fit via least squares on lag-1)."""
    if len(returns) < 3:
        return 0.0, 1.0
    x = returns[:-1]
    y = returns[1:]
    A = np.column_stack([x, np.ones_like(x)])
    (a, b), *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(a), float(b)


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

    window = closes[-WINDOW:] if len(closes) >= WINDOW else closes
    returns = np.diff(window) / window[:-1]

    a, b = _fit_linear_ssm(returns)
    # roll the fitted recursion forward one step from the last observed
    # return to get the SSM's hidden-state-implied next return
    h = float(returns[-1])
    next_state = a * h + b * h
    movement = "up" if next_state > 0 else ("down" if next_state < 0 else "flat")
    # confidence: squash the recursion magnitude relative to recent return
    # volatility into (0, 1) via a logistic-style transform
    resid_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 1e-6
    confidence = float(1.0 / (1.0 + np.exp(-abs(next_state) / max(resid_std, 1e-8))))

    last_close = float(closes[-1])
    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(closes)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "graph_note": GRAPH_NOTE,
        "ssm_window": int(len(window)),
        "ssm_a": a,
        "ssm_b": b,
        "predicted_movement": movement,
        "predicted_next_state_return": next_state,
        "movement_confidence": confidence,
        "last_close": last_close,
        "predicted_next_close": last_close * (1 + next_state),
    }
    return pd.DataFrame([result])
