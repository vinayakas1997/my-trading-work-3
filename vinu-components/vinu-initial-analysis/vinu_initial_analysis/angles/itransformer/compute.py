"""iTransformer — cross-variate correlation transformer, method 21 of the
32-method plan (see 21-itransformer.md). Inverts the usual transformer
setup: instead of tokenizing time steps, it tokenizes *variates*, so
self-attention runs across variate-tokens and can learn which series move
together.

Spec deviation, documented: 21-itransformer.md's "Input" section calls for
"a historical window across multiple variates/tickers fed jointly" — true
cross-*asset* attention over sibling tickers. This angle's `compute()` is
invoked per-symbol with only that symbol's `bars` (the runner's
`_run_angle` calls every angle the same way; there is no sibling-ticker
bars parameter, and wiring a live multi-ticker fetch has no deterministic
test story without a real price_client). We instead apply the *same*
architectural idea — attention across variate-tokens — to this single
symbol's OHLCV **channels** (open/high/low/close/volume) as the variates:
each channel's full lookback window is embedded as one token, and
self-attention runs across those channel-tokens. This is a genuine,
testable instance of iTransformer's core mechanism (variate-token
attention), just with channels standing in for tickers; it does not
capture true cross-*asset* correlation. `close` is reported as the
primary forecast channel.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "itransformer"

CHANNELS = ["open", "high", "low", "close", "volume"]

# Same LOOKBACK/MIN_BARS rationale as the other point-forecast angles here:
# 32-step windows with ~90 bars gives ~55 training samples, enough for a
# tiny (few-thousand-param) transformer to fit without pure memorization.
LOOKBACK = 32
D_MODEL = 16
NHEAD = 2
NUM_LAYERS = 1
# Decided value, 04-enhancement-of-each-angle/09-itransformer.md — raised
# from 90, same consistency move as ARIMA/DLinear/exponential_smoothing.
MIN_BARS = 100
EPOCHS = 50


def _direction(forecast_return: float, eps: float = 1e-4) -> str:
    if forecast_return > eps:
        return "up"
    if forecast_return < -eps:
        return "down"
    return "flat"


def _make_windows(channels: np.ndarray, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    # channels: (n_channels, n_timesteps)
    n_channels, n = channels.shape
    xs, ys = [], []
    for i in range(n - lookback):
        xs.append(channels[:, i:i + lookback])
        ys.append(channels[:, i + lookback])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


def _build_model(lookback: int, n_channels: int):
    from torch import nn

    class ITransformer(nn.Module):
        """Variate-as-token transformer: each channel's whole window is one
        token; attention runs across the (small) set of channel-tokens."""

        def __init__(self):
            super().__init__()
            self.embed = nn.Linear(lookback, D_MODEL)
            layer = nn.TransformerEncoderLayer(
                d_model=D_MODEL, nhead=NHEAD, dim_feedforward=D_MODEL * 2,
                dropout=0.1, batch_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=NUM_LAYERS)
            self.head = nn.Linear(D_MODEL, 1)

        def forward(self, x):  # x: (batch, n_channels, lookback)
            tok = self.embed(x)               # (batch, n_channels, d_model)
            enc = self.encoder(tok)            # attention across channel-tokens
            return self.head(enc).squeeze(-1)  # (batch, n_channels)

    return ITransformer()


def _fit_and_forecast(bars: pd.DataFrame, available: list[str], seed: int = 42):
    """Trains a fresh iTransformer model on `bars`' channels and forecasts
    one step past the end. Returns (fields, model): `fields` includes a
    forecast for **every** channel (`forecast_open`/`forecast_high`/
    `forecast_low`/`forecast_close`/`forecast_volume`, whichever are
    present), not just close — the model already computes all of them
    internally as part of its normal forward pass; the original code
    computed `forecast_all` but only ever extracted `close`, discarding
    the other 4 channels' real, free output. Fixed here per the decided
    design (04-enhancement-of-each-angle/09-itransformer.md SS3/SS7).
    `model` is the trained nn.Module, exposed so the walk-forward backtest
    (backtest.py) can save its state_dict as this step's weights artifact.

    Raises ValueError if there aren't enough training windows.
    """
    import torch
    from torch import nn

    torch.manual_seed(seed)
    close_idx = available.index("close")

    raw = np.stack([bars[c].astype(float).values for c in available], axis=0)  # (n_channels, n)
    means = raw.mean(axis=1, keepdims=True)
    stds = raw.std(axis=1, keepdims=True)
    stds[stds < 1e-8] = 1.0
    norm = (raw - means) / stds

    X, y = _make_windows(norm, LOOKBACK)
    if len(X) < 20:
        raise ValueError(f"insufficient training windows: {len(X)}")

    X_t = torch.from_numpy(X)  # (batch, n_channels, lookback)
    y_t = torch.from_numpy(y)  # (batch, n_channels)

    model = _build_model(LOOKBACK, len(available))
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
        last_window = torch.from_numpy(norm[:, -LOOKBACK:].astype(np.float32)).unsqueeze(0)
        forecast_norm = model(last_window).squeeze(0).numpy()  # (n_channels,)

    forecast_all = forecast_norm * stds.squeeze(-1) + means.squeeze(-1)
    forecast_price = float(forecast_all[close_idx])
    last_close = float(raw[close_idx, -1])
    forecast_return = (forecast_price - last_close) / last_close if last_close else 0.0

    fields: dict[str, Any] = {
        "status": "ok",
        "n_observations": raw.shape[1],
        "n_train_windows": int(len(X)),
        "lookback": LOOKBACK,
        "channels": ",".join(available),
        "n_channels": len(available),
        "last_close": last_close,
        "forecast_price": forecast_price,
        "forecast_return": float(forecast_return),
        "direction": _direction(forecast_return),
        "train_loss": final_train_loss,
    }
    for ch, value in zip(available, forecast_all):
        fields[f"forecast_{ch}"] = float(value)
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

    available = [c for c in CHANNELS if c in bars.columns]
    if "close" not in available:
        available = ["close"]  # already guaranteed above, but keep close first

    n = len(bars)
    if n < MIN_BARS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(n),
        }])

    try:
        fields, _model = _fit_and_forecast(bars, available, seed=seed)
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
