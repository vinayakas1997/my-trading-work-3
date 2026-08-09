"""LPatchTST — LSTM + PatchTST hybrid, method 23 of the 32-method plan (see
23-lpatchtst.md). "L" = LSTM, not "lightweight": per the spec's own title
("LSTM+PatchTST") and explanation ("Combines the two architectures: LSTM
layers capture sequential dependencies, PatchTST-style patching and
channel-independent attention add the regularization benefit..."), this is
a genuine two-branch hybrid, not a smaller config of `patchtst`.

The reported best-of-six performer (~54% directional accuracy, Sharpe
2.31-2.32). Architecture: an LSTM branch consumes the raw lookback window
sequentially; a `PatchEncoderBranch` (imported from `patchtst` — see that
module's `_patch_transformer.py` docstring for why it's shared) processes
the same window as patches; the two branches' final representations are
concatenated and passed through one linear head for the point forecast.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.patchtst._patch_transformer import (
    PatchEncoderBranch,
    direction,
    make_windows,
    zscore,
)

ANGLE_NAME = "lpatchtst"

# Same lookback/patch config as patchtst so the two branches see the same
# window; MIN_BARS=90 for the same "~55 training windows" rationale as the
# other point-forecast angles in this batch.
LOOKBACK = 32
PATCH_LEN = 8
STRIDE = 4
D_MODEL = 16
NHEAD = 2
NUM_LAYERS = 1
LSTM_HIDDEN = 16
# Decided value, 04-enhancement-of-each-angle/13-lpatchtst.md — raised
# from 90, same consistency move as ARIMA/DLinear.
MIN_BARS = 100
EPOCHS = 50


def _build_model():
    import torch
    from torch import nn

    patch_branch = PatchEncoderBranch(
        lookback=LOOKBACK, patch_len=PATCH_LEN, stride=STRIDE,
        d_model=D_MODEL, nhead=NHEAD, num_layers=NUM_LAYERS,
    )

    class LPatchTST(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=LSTM_HIDDEN, num_layers=1, batch_first=True)
            self.patch_branch = patch_branch
            self.head = nn.Linear(LSTM_HIDDEN + patch_branch.out_dim, 1)

        def forward(self, x):  # x: (batch, lookback)
            _, (h_n, _) = self.lstm(x.unsqueeze(-1))
            lstm_repr = h_n[-1]                              # (batch, LSTM_HIDDEN)
            patch_repr = self.patch_branch.encode_flat(x)     # (batch, out_dim)
            combined = torch.cat([lstm_repr, patch_repr], dim=-1)
            return self.head(combined)

    return LPatchTST(), patch_branch


def _fit_and_forecast(close: np.ndarray, seed: int = 42):
    """Trains a fresh LPatchTST model on `close` and forecasts one step
    past its end. Returns (fields, model) — `fields` is every result
    column except symbol/analysis_at/angle (callers attach those), and
    `model` is the trained nn.Module, exposed so the walk-forward
    backtest (backtest.py) can save its state_dict as this step's
    weights artifact.

    Raises ValueError if there aren't enough training windows.
    """
    import torch
    from torch import nn

    torch.manual_seed(seed)

    norm, mean, std = zscore(close)
    X, y = make_windows(norm, LOOKBACK, horizon=1)
    if len(X) < 20:
        raise ValueError(f"insufficient training windows: {len(X)}")

    X_t = torch.from_numpy(X)
    y_t = torch.from_numpy(y)

    model, patch_branch = _build_model()
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(EPOCHS):
        opt.zero_grad()
        pred = model(X_t)
        loss = loss_fn(pred, y_t)
        loss.backward()
        opt.step()
    final_train_loss = float(loss.item())

    model.eval()
    with torch.no_grad():
        last_window = torch.from_numpy(norm[-LOOKBACK:].astype(np.float32)).unsqueeze(0)
        forecast_norm = float(model(last_window).item())

    forecast_price = forecast_norm * std + mean
    last_close = float(close[-1])
    forecast_return = (forecast_price - last_close) / last_close if last_close else 0.0

    fields = {
        "status": "ok",
        "n_observations": int(len(close)),
        "n_train_windows": int(len(X)),
        "lookback": LOOKBACK,
        "lstm_hidden_size": LSTM_HIDDEN,
        "n_patches": patch_branch.n_patches,
        "last_close": last_close,
        "forecast_price": float(forecast_price),
        "forecast_return": float(forecast_return),
        "direction": direction(forecast_return),
        "train_loss": final_train_loss,
    }
    return fields, model


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

    try:
        fields, _model = _fit_and_forecast(close, seed=seed)
    except ValueError:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(n),
        }])

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **fields,
    }
    return pd.DataFrame([result])
