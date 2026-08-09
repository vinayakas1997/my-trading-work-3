"""LSTM — sequential-nonlinearity baseline, method 19 of the 32-method plan
(see 19-lstm.md). A classical recurrent network with gated memory cells,
processing the price sequence one step at a time and carrying forward a
learned hidden state.

Per 19-lstm.md's "Output format": "A point forecast (predicted next-step
price/return), thresholded to a direction for the reported ~51%
directional-accuracy figure." The same note flags that "lightweight
LSTM/GRU/Mamba often beat huge transformers on financial data" — so this
stays a genuinely small (single-layer, small hidden size) recurrent net
rather than a token gesture.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "lstm"

# Same rationale as dlinear/patchtst: LOOKBACK=30 with MIN_BARS=80 gives
# ~50 training windows, plenty for a single-layer, 16-unit LSTM (well under
# 50k params) to fit in a handful of epochs without over/underfitting on
# noise alone.
LOOKBACK = 30
# Decided value, 04-enhancement-of-each-angle/14-lstm.md — raised from
# 80, same consistency move as ARIMA/DLinear/LPatchTST. Overridable via
# VINU_LSTM_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_BARS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)
HIDDEN_SIZE = 16
EPOCHS = 60


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


def _build_model(hidden_size: int):
    from torch import nn

    class LSTMForecaster(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(input_size=1, hidden_size=hidden_size, num_layers=1, batch_first=True)
            self.head = nn.Linear(hidden_size, 1)

        def forward(self, x):  # x: (batch, lookback, 1)
            out, (h_n, _) = self.lstm(x)
            return self.head(h_n[-1])

    return LSTMForecaster()


def _fit_and_forecast(close: np.ndarray, seed: int = 42):
    """Trains a fresh single-layer LSTM on `close` and forecasts one step
    past its end. Returns (fields, model) — `fields` is every result
    column except symbol/analysis_at/angle (callers attach those), and
    `model` is the trained nn.Module, exposed so the walk-forward backtest
    (backtest.py) can save its state_dict as this step's weights artifact.

    Raises ValueError if there aren't enough training windows.
    """
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
        raise ValueError(f"insufficient training windows: {len(X)}")

    X_t = torch.from_numpy(X).unsqueeze(-1)  # (batch, lookback, 1)
    y_t = torch.from_numpy(y).unsqueeze(-1)

    model = _build_model(HIDDEN_SIZE)
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
        last_window = torch.from_numpy(norm[-LOOKBACK:].astype(np.float32)).reshape(1, LOOKBACK, 1)
        forecast_norm = float(model(last_window).item())

    forecast_price = forecast_norm * std + mean
    last_close = float(close[-1])
    forecast_return = (forecast_price - last_close) / last_close if last_close else 0.0

    fields = {
        "status": "ok",
        "n_observations": int(len(close)),
        "n_train_windows": int(len(X)),
        "lookback": LOOKBACK,
        "hidden_size": HIDDEN_SIZE,
        "last_close": last_close,
        "forecast_price": float(forecast_price),
        "forecast_return": float(forecast_return),
        "direction": _direction(forecast_return),
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
