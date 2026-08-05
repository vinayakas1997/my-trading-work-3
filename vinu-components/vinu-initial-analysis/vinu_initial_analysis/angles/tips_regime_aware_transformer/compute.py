"""TIPS — Transformer with Inductive Prior Synthesis (regime-aware),
method 24 of the 32-method plan (see 24-tips-regime-aware-transformer.md).
"Synthesizes an inductive prior tuned to the current detected regime" —
i.e. the model's structure, not just its input, changes with the detected
regime (momentum vs. mean-reversion).

Two components, both required by the spec (don't drop the regime piece):

1. Regime detection (`_detect_regime`): a purely statistical, non-torch
   step — the lag-1 autocorrelation of returns over a trailing window.
   Positive autocorrelation means recent up-moves tend to be followed by
   further up-moves (momentum); negative means recent moves tend to
   reverse (mean-reversion). This is the "internally infers/conditions on
   the current regime" input the spec calls for, computed once per
   sliding window at train time and once for the live window at inference.

2. Regime-conditioned forecasting: a shared per-time-step transformer
   encoder produces a pooled representation, then **two separate linear
   output heads** — one "tuned" to momentum windows, one to
   mean-reversion windows. Which head produces a given sample's forecast
   is selected by that sample's detected regime (via `torch.where`, so
   gradients only flow to the head responsible for each regime's samples)
   — this is the literal "structural" regime adaptation the spec
   describes (different learned bias per regime), rather than merely
   concatenating a regime flag into one shared head.

Per the spec's "Output format": "A price/return forecast conditioned on an
internally-detected regime state — likely also exposes the detected
regime label... as an auxiliary output." Both are returned below.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "tips_regime_aware_transformer"

REGIME_MOMENTUM = 0
REGIME_MEAN_REVERSION = 1

# Needs: a REGIME_WINDOW-bar trailing autocorrelation per sample, plus a
# LOOKBACK-bar transformer window per sample, plus ~20+ training samples.
# 120 bars gives roughly (120 - LOOKBACK - REGIME_WINDOW) ~= 40 usable
# windows -- enough margin for both the regime statistic and the model fit
# to be meaningful rather than noise.
LOOKBACK = 24
REGIME_WINDOW = 20
MIN_BARS = 120
D_MODEL = 16
NHEAD = 2
NUM_LAYERS = 1
EPOCHS = 50


def _direction(forecast_return: float, eps: float = 1e-4) -> str:
    if forecast_return > eps:
        return "up"
    if forecast_return < -eps:
        return "down"
    return "flat"


def _rolling_autocorr_lag1(returns: np.ndarray, window: int) -> np.ndarray:
    """Lag-1 autocorrelation of `returns` over a trailing `window`, for
    every index where a full trailing window exists. NaN elsewhere."""
    s = pd.Series(returns)
    out = np.full(len(returns), np.nan)
    for i in range(window, len(returns) + 1):
        seg = s.iloc[i - window:i]
        if seg.std() > 1e-12:
            ac = seg.autocorr(lag=1)
            out[i - 1] = 0.0 if pd.isna(ac) else ac
        else:
            out[i - 1] = 0.0
    return out


def _regime_label(autocorr: float) -> int:
    return REGIME_MOMENTUM if autocorr >= 0 else REGIME_MEAN_REVERSION


def _regime_name(label: int) -> str:
    return "momentum" if label == REGIME_MOMENTUM else "mean_reversion"


def _make_windows(norm: np.ndarray, regime_labels: np.ndarray, lookback: int):
    """norm/regime_labels are aligned 1-D arrays over the same index range.
    Builds (X window, y next value, regime label at the window's end)."""
    n = len(norm)
    xs, ys, regimes = [], [], []
    for i in range(n - lookback):
        end = i + lookback
        if np.isnan(regime_labels[end - 1]):
            continue
        xs.append(norm[i:end])
        ys.append(norm[end])
        regimes.append(regime_labels[end - 1])
    return (
        np.asarray(xs, dtype=np.float32),
        np.asarray(ys, dtype=np.float32),
        np.asarray(regimes, dtype=np.int64),
    )


def _build_model():
    import torch
    from torch import nn

    class TIPSCore(nn.Module):
        def __init__(self):
            super().__init__()
            self.token_embed = nn.Linear(1, D_MODEL)
            self.pos = nn.Parameter(torch.zeros(1, LOOKBACK, D_MODEL))
            layer = nn.TransformerEncoderLayer(
                d_model=D_MODEL, nhead=NHEAD, dim_feedforward=D_MODEL * 2,
                dropout=0.1, batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=NUM_LAYERS)
            self.momentum_head = nn.Linear(D_MODEL, 1)
            self.mean_reversion_head = nn.Linear(D_MODEL, 1)

        def forward(self, x, regime_labels):
            # x: (batch, lookback); regime_labels: (batch,) int64 0/1
            tok = self.token_embed(x.unsqueeze(-1)) + self.pos  # (batch, lookback, d_model)
            enc = self.encoder(tok)
            pooled = enc.mean(dim=1)  # (batch, d_model)
            pred_momentum = self.momentum_head(pooled)
            pred_mean_rev = self.mean_reversion_head(pooled)
            is_momentum = (regime_labels == REGIME_MOMENTUM).unsqueeze(-1)
            return torch.where(is_momentum, pred_momentum, pred_mean_rev)

    return TIPSCore()


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    analysis_at = datetime.now(timezone.utc).isoformat()

    if bars is None or bars.empty or "close" not in bars.columns:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "no_data",
        }])

    close = bars["close"].astype(float).values
    n = len(close)

    if n < MIN_BARS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(n),
        }])

    returns = np.diff(close) / close[:-1]
    autocorr = _rolling_autocorr_lag1(returns, REGIME_WINDOW)  # aligned to returns (len n-1)

    mean = float(close.mean())
    std = float(close.std())
    if std < 1e-8:
        std = 1.0
    norm = (close - mean) / std

    # Regime label at price-index i is derived from the return series
    # ending at i (i.e. regime_labels[i] uses autocorr[i-1], since returns
    # has one fewer element than close). Pad with NaN at index 0 so
    # indices line up 1:1 with `norm`/`close`.
    regime_autocorr_by_close_idx = np.concatenate([[np.nan], autocorr])
    regime_labels_by_close_idx = np.array(
        [np.nan if np.isnan(a) else _regime_label(a) for a in regime_autocorr_by_close_idx]
    )

    X, y, regimes = _make_windows(norm, regime_labels_by_close_idx, LOOKBACK)
    if len(X) < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(n),
        }])

    import torch
    from torch import nn

    torch.manual_seed(seed)

    X_t = torch.from_numpy(X)
    y_t = torch.from_numpy(y).unsqueeze(-1)
    regime_t = torch.from_numpy(regimes)

    model = _build_model()
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(EPOCHS):
        opt.zero_grad()
        pred = model(X_t, regime_t)
        loss = loss_fn(pred, y_t)
        loss.backward()
        opt.step()
    final_train_loss = float(loss.item())

    # Live regime + forecast from the most recent window.
    current_autocorr = float(regime_autocorr_by_close_idx[-1])
    if np.isnan(current_autocorr):
        current_autocorr = 0.0
    current_regime = _regime_label(current_autocorr)

    model.eval()
    with torch.no_grad():
        last_window = torch.from_numpy(norm[-LOOKBACK:].astype(np.float32)).unsqueeze(0)
        last_regime_t = torch.tensor([current_regime], dtype=torch.int64)
        forecast_norm = float(model(last_window, last_regime_t).item())

    forecast_price = forecast_norm * std + mean
    last_close = float(close[-1])
    forecast_return = (forecast_price - last_close) / last_close if last_close else 0.0

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(n),
        "n_train_windows": int(len(X)),
        "lookback": LOOKBACK,
        "regime_window": REGIME_WINDOW,
        "last_close": last_close,
        "forecast_price": float(forecast_price),
        "forecast_return": float(forecast_return),
        "direction": _direction(forecast_return),
        "regime": _regime_name(current_regime),
        "regime_autocorr": current_autocorr,
        "n_momentum_windows": int((regimes == REGIME_MOMENTUM).sum()),
        "n_mean_reversion_windows": int((regimes == REGIME_MEAN_REVERSION).sum()),
        "train_loss": final_train_loss,
    }
    return pd.DataFrame([result])
