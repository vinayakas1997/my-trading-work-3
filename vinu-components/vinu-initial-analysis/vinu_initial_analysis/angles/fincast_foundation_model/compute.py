"""FinCast — a second financial time-series foundation model (ACM CIKM 2026).

See ../../../New-talk-/Final-implementation/01-present-considerations/
30-fincast-foundation-model.md (method 30): a decoder-only, sparse
Mixture-of-Experts transformer (1B params, 4 experts, top-k=2 routing),
same general category as Kronos — a Kronos-class financial-K-line
foundation model, autoregressive over price windows.

**Backend: fallback_proxy — no install attempt was made, by design.**
The spec's own text flags this one directly: FinCast is "borderline on
limitation #2" (~2GB fp16 / ~4GB fp32) and no PyPI package or
self-hostable checkpoint reference is given anywhere in the spec — only
two paper links (ACM DOI + arXiv preprint). Per this batch's explicit
instruction ("if either says the model's public availability is
unconfirmed ... implement the fallback-proxy path directly, don't waste
time hunting for a nonexistent package"), no `pip install`/download was
attempted here. Instead: a small in-process-trained PyTorch MLP predicts
the next K-line's OHLC from a window of recent bars — structurally the
same "financial K-line autoregressive forecast" task FinCast targets, at
a scale this can actually run, with an explicit MoE-style routing note
absent (this proxy is a single dense head, not a mixture of experts).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "fincast_foundation_model"
MIN_OBSERVATIONS = 30
CONTEXT_WINDOW = 32
FALLBACK_REASON = (
    "FinCast's spec (30-fincast-foundation-model.md) gives no PyPI "
    "package or self-hostable checkpoint — only paper links (ACM DOI + "
    "arXiv) — and flags itself as borderline/unconfirmed on public "
    "availability at the stated 1B-param MoE size. Per this batch's "
    "instruction to skip hunting for a nonexistent package in that case, "
    "using an in-process-trained small PyTorch MLP proxy over next-K-line "
    "regression (a single dense head, not the real sparse MoE)."
)


class _NextBarMLP:
    def __init__(self, n_features: int, hidden: int = 8):
        import torch

        self.torch = torch
        self.net = torch.nn.Sequential(
            torch.nn.Linear(n_features, hidden),
            torch.nn.Tanh(),
            torch.nn.Linear(hidden, 4),
        )

    def fit_predict(self, X: np.ndarray, y: np.ndarray, x_last: np.ndarray) -> np.ndarray:
        torch = self.torch
        X_t = torch.tensor(X, dtype=torch.float32)
        y_t = torch.tensor(y, dtype=torch.float32)
        opt = torch.optim.Adam(self.net.parameters(), lr=0.02)
        loss_fn = torch.nn.MSELoss()
        for _ in range(60):
            opt.zero_grad()
            pred = self.net(X_t)
            loss = loss_fn(pred, y_t)
            loss.backward()
            opt.step()
        with torch.no_grad():
            x_last_t = torch.tensor(x_last, dtype=torch.float32).unsqueeze(0)
            return self.net(x_last_t).squeeze(0).numpy()


def _build_windows(ohlc: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(ohlc)
    xs, ys = [], []
    for i in range(window, n):
        xs.append(ohlc[i - window:i].flatten())
        ys.append(ohlc[i])
    return np.array(xs), np.array(ys), ohlc[n - window:n].flatten()


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

    required_cols = {"open", "high", "low", "close"}
    if not required_cols.issubset(bars.columns) or len(bars) < MIN_OBSERVATIONS + CONTEXT_WINDOW:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(bars)),
        }])

    ohlc_raw = bars[["open", "high", "low", "close"]].astype(float).values
    prev_close = np.roll(ohlc_raw[:, 3], 1)
    prev_close[0] = ohlc_raw[0, 3]
    log_returns = np.log(np.clip(ohlc_raw, 1e-8, None)) - np.log(np.clip(prev_close, 1e-8, None))[:, None]

    X, y, x_last = _build_windows(log_returns, CONTEXT_WINDOW)
    model = _NextBarMLP(n_features=X.shape[1])
    next_bar_log_ret = model.fit_predict(X, y, x_last)

    last_close = float(ohlc_raw[-1, 3])
    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(len(ohlc_raw)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "context_window": CONTEXT_WINDOW,
        "predicted_next_open": float(last_close * np.exp(next_bar_log_ret[0])),
        "predicted_next_high": float(last_close * np.exp(next_bar_log_ret[1])),
        "predicted_next_low": float(last_close * np.exp(next_bar_log_ret[2])),
        "predicted_next_close": float(last_close * np.exp(next_bar_log_ret[3])),
        "last_close": last_close,
    }
    return pd.DataFrame([result])
