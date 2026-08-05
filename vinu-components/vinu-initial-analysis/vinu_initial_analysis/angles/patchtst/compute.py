"""PatchTST — channel-independent patch transformer, method 20 of the
32-method plan (see 20-patchtst.md). Splits the lookback window into
fixed-length patches (like ViT patches an image), embeds each patch as a
token, and runs standard transformer self-attention across patches.

Per 20-patchtst.md's "Output format": "A point forecast per channel (price
series)... thresholded to direction for the ~50% figure." We run on the
single `close` channel (channel independence means additional channels
would each get their own independent forecast rather than being mixed —
out of scope for the single-series `bars` this angle receives, see
`itransformer` for the cross-channel-attention counterpart).

Uses the shared `PatchEncoderBranch` from `_patch_transformer.py` — see
that module's docstring for why it's shared with `lpatchtst`.
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

ANGLE_NAME = "patchtst"

# LOOKBACK=32 with PATCH_LEN=8/STRIDE=4 gives 7 patch tokens — enough for
# self-attention to do something meaningful without being pure overhead.
# MIN_BARS=90 leaves ~55 training windows after the lookback, comfortably
# above the ~20-sample floor below which a transformer this size is just
# memorizing.
LOOKBACK = 32
PATCH_LEN = 8
STRIDE = 4
D_MODEL = 16
NHEAD = 2
NUM_LAYERS = 1
MIN_BARS = 90
EPOCHS = 50


def _build_model():
    from torch import nn

    branch = PatchEncoderBranch(
        lookback=LOOKBACK, patch_len=PATCH_LEN, stride=STRIDE,
        d_model=D_MODEL, nhead=NHEAD, num_layers=NUM_LAYERS,
    )

    class PatchTSTModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.branch = branch
            self.head = nn.Linear(branch.out_dim, 1)

        def forward(self, x):
            return self.head(self.branch.encode_flat(x))

    return PatchTSTModel()


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

    import torch
    from torch import nn

    torch.manual_seed(seed)

    norm, mean, std = zscore(close)
    X, y = make_windows(norm, LOOKBACK, horizon=1)
    if len(X) < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(n),
        }])

    X_t = torch.from_numpy(X)
    y_t = torch.from_numpy(y)

    model = _build_model()
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

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "n_observations": int(n),
        "n_train_windows": int(len(X)),
        "lookback": LOOKBACK,
        "patch_len": PATCH_LEN,
        "n_patches": model.branch.n_patches,
        "last_close": last_close,
        "forecast_price": float(forecast_price),
        "forecast_return": float(forecast_return),
        "direction": direction(forecast_return),
        "train_loss": final_train_loss,
    }
    return pd.DataFrame([result])
