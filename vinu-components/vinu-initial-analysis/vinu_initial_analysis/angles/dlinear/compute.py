"""DLinear — decomposition-based linear model, method 18 of the 32-method
plan (see 18-dlinear.md). Simplest of the six trained-from-scratch
architectures the source survey covers: no attention, no nonlinearity —
just a moving-average trend/seasonal decomposition and two linear layers.

Per 18-dlinear.md's "Output format": "A point forecast (a single predicted
value or short vector of predicted returns/prices) — the linear layer's
direct output, then thresholded to a direction for the reported ~50%
directional-accuracy figure." We forecast one step ahead and threshold the
predicted return to a direction.

This is a genuine (if tiny) from-scratch fit: the model is built and its
two linear layers are trained via a handful of Adam epochs on sliding
windows of `bars["close"]` every time `compute()` runs — not a hardcoded
number and not a pre-trained checkpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "dlinear"

# A window needs at least LOOKBACK points to form one training sample plus
# a handful of samples to actually learn anything (not just memorize a
# single example) plus one held-out window to produce the live forecast.
# 80 bars gives ~50 training windows at LOOKBACK=30, which is enough for
# this small a model (well under 1k params) to fit meaningfully fast.
LOOKBACK = 30
MIN_BARS = 80
EPOCHS = 60
KERNEL_SIZE = 5  # odd, so 'same' padding keeps trend length == input length


def _direction(forecast_return: float, eps: float = 1e-4) -> str:
    if forecast_return > eps:
        return "up"
    if forecast_return < -eps:
        return "down"
    return "flat"


def _make_windows(series: np.ndarray, lookback: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(series)
    xs, ys = [], []
    for i in range(n - lookback):
        xs.append(series[i:i + lookback])
        ys.append(series[i + lookback])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


def _build_model(lookback: int, kernel_size: int):
    import torch
    from torch import nn

    class DLinear(nn.Module):
        def __init__(self):
            super().__init__()
            pad = kernel_size // 2
            self.avg = nn.AvgPool1d(kernel_size=kernel_size, stride=1, padding=pad)
            self.linear_trend = nn.Linear(lookback, 1)
            self.linear_seasonal = nn.Linear(lookback, 1)

        def forward(self, x):  # x: (batch, lookback)
            trend = self.avg(x.unsqueeze(1)).squeeze(1)
            if trend.shape[1] != x.shape[1]:
                trend = trend[:, :x.shape[1]]
            seasonal = x - trend
            return self.linear_trend(trend) + self.linear_seasonal(seasonal)

    return DLinear()


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

    mean = float(close.mean())
    std = float(close.std())
    if std < 1e-8:
        std = 1.0
    norm = (close - mean) / std

    X, y = _make_windows(norm, LOOKBACK)
    if len(X) < 20:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(n),
        }])

    X_t = torch.from_numpy(X)
    y_t = torch.from_numpy(y).unsqueeze(-1)

    model = _build_model(LOOKBACK, KERNEL_SIZE)
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
        "last_close": last_close,
        "forecast_price": float(forecast_price),
        "forecast_return": float(forecast_return),
        "direction": _direction(forecast_return),
        "train_loss": final_train_loss,
    }
    return pd.DataFrame([result])
