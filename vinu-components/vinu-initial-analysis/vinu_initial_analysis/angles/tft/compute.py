"""TFT — Temporal Fusion Transformer, method 22 of the 32-method plan (see
22-tft.md). Combines LSTM-style sequence processing with a
variable-selection network (learns which input features matter at each
step) and multi-head attention.

Per 22-tft.md's "Output format": "Natively quantile forecasts (e.g.
P10/P50/P90), a signature feature of the... architecture — richer than a
single point estimate." We implement:
  1. A variable-selection network: a small gated linear layer that learns
     per-feature softmax weights, applied to the engineered feature vector
     at every time step before it enters the LSTM — this is the piece the
     spec credits for "filtering noise other models don't."
  2. An LSTM encoder over the (gated) feature sequence.
  3. Self-attention over the LSTM's per-step outputs (the "interpretable
     multi-head attention" piece).
  4. Three linear heads producing P10/P50/P90 next-step return forecasts,
     trained jointly with the pinball (quantile) loss.

Known-future inputs / static covariates (earnings calendar, sector) from
the spec's "Input" section are not modeled — `bars`/`news` as passed to
`compute()` don't carry that schema, and adding it would require inventing
data this environment doesn't have. Everything else (variable selection,
LSTM+attention, quantile heads/loss) is implemented per spec.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "tft"

FEATURE_NAMES = ["ret_1", "ret_5", "sma_ratio_5", "sma_ratio_21", "vol_5", "high_low_range"]
QUANTILES = (0.1, 0.5, 0.9)

# LOOKBACK=30 timesteps of a 6-feature vector, needing a 21-bar SMA warmup
# before features are valid, plus ~20+ training windows -> MIN_BARS=90
# leaves a comfortable margin (~35 usable windows).
LOOKBACK = 30
# Decided value, 04-enhancement-of-each-angle/26-tft.md — raised from 90,
# same consistency move as every other trained-from-scratch angle.
# Overridable via VINU_TFT_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_BARS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)
HIDDEN_SIZE = 16
EPOCHS = 60


def _build_features(bars: pd.DataFrame) -> pd.DataFrame:
    close = bars["close"].astype(float)
    high = bars["high"].astype(float) if "high" in bars.columns else close
    low = bars["low"].astype(float) if "low" in bars.columns else close
    ret = close.pct_change()
    feats = pd.DataFrame({
        "ret_1": ret,
        "ret_5": close.pct_change(5),
        "sma_ratio_5": close.rolling(5).mean() / close - 1,
        "sma_ratio_21": close.rolling(21).mean() / close - 1,
        "vol_5": ret.rolling(5).std(),
        "high_low_range": (high - low) / close,
    })
    return feats


def _make_windows(features: np.ndarray, target: np.ndarray, lookback: int):
    n = len(features)
    xs, ys = [], []
    for i in range(n - lookback):
        xs.append(features[i:i + lookback])
        ys.append(target[i + lookback])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


def _build_model(n_features: int, hidden_size: int):
    import torch
    from torch import nn

    class VariableSelection(nn.Module):
        """Learns a softmax weight per feature, applied elementwise at each
        time step — the spec's "variable-selection network that learns to
        weight which input features matter at each time step"."""

        def __init__(self):
            super().__init__()
            self.gate = nn.Sequential(nn.Linear(n_features, n_features), nn.Softmax(dim=-1))

        def forward(self, x):  # x: (batch, seq, n_features)
            weights = self.gate(x)
            return x * weights * n_features, weights

    class TFTLite(nn.Module):
        def __init__(self):
            super().__init__()
            self.var_select = VariableSelection()
            self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden_size, num_layers=1, batch_first=True)
            self.attn = nn.MultiheadAttention(embed_dim=hidden_size, num_heads=2, batch_first=True)
            # Median head plus two non-negative deltas (softplus-ed) added/
            # subtracted from it, rather than three independent heads — this
            # guarantees P10 <= P50 <= P90 by construction (no quantile
            # crossing), a standard fix for independently-trained quantile
            # regression heads.
            self.median_head = nn.Linear(hidden_size, 1)
            self.delta_head = nn.Linear(hidden_size, 2)

        def forward(self, x):
            gated, weights = self.var_select(x)
            lstm_out, _ = self.lstm(gated)
            attn_out, _ = self.attn(lstm_out, lstm_out, lstm_out)
            pooled = attn_out[:, -1, :]  # last time step's attended representation
            median = self.median_head(pooled)
            deltas = nn.functional.softplus(self.delta_head(pooled))  # (batch, 2), both >= 0
            low = median - deltas[:, 0:1]
            high = median + deltas[:, 1:2]
            preds = torch.cat([low, median, high], dim=-1)  # (batch, 3) == p10, p50, p90
            return preds, weights

    return TFTLite()


def _pinball_loss(preds, target):
    import torch
    losses = []
    for i, q in enumerate(QUANTILES):
        err = target - preds[:, i:i + 1]
        losses.append(torch.max((q - 1) * err, q * err))
    return torch.cat(losses, dim=1).mean()


def _fit_and_forecast(bars: pd.DataFrame, seed: int = 42):
    """Trains a fresh TFT-lite model on `bars` and forecasts one step
    past its end. Returns (fields, model) — `fields` is every result
    column except symbol/analysis_at/angle (callers attach those), and
    `model` is the trained nn.Module, exposed so the walk-forward
    backtest (backtest.py) can save its state_dict as this step's
    weights artifact.

    Raises ValueError if there isn't enough usable feature/window data.
    """
    n = len(bars)
    feats_df = _build_features(bars).reset_index(drop=True)
    close = bars["close"].astype(float).reset_index(drop=True)
    ret_next = close.pct_change().shift(-1)  # target: next-step return

    combined = pd.concat([feats_df, ret_next.rename("target")], axis=1).dropna()
    if len(combined) < LOOKBACK + 20:
        raise ValueError(f"insufficient feature rows: {len(combined)}")

    feat_vals = combined[FEATURE_NAMES].values.astype(np.float32)
    f_mean = feat_vals.mean(axis=0, keepdims=True)
    f_std = feat_vals.std(axis=0, keepdims=True)
    f_std[f_std < 1e-8] = 1.0
    feat_norm = (feat_vals - f_mean) / f_std
    target_vals = combined["target"].values.astype(np.float32)

    X, y = _make_windows(feat_norm, target_vals, LOOKBACK)
    if len(X) < 15:
        raise ValueError(f"insufficient training windows: {len(X)}")

    import torch

    torch.manual_seed(seed)

    X_t = torch.from_numpy(X)
    y_t = torch.from_numpy(y).unsqueeze(-1)

    model = _build_model(len(FEATURE_NAMES), HIDDEN_SIZE)
    opt = torch.optim.Adam(model.parameters(), lr=0.01)

    model.train()
    for _ in range(EPOCHS):
        opt.zero_grad()
        preds, _ = model(X_t)
        loss = _pinball_loss(preds, y_t)
        loss.backward()
        opt.step()
    final_train_loss = float(loss.item())

    model.eval()
    with torch.no_grad():
        last_window = torch.from_numpy(feat_norm[-LOOKBACK:].astype(np.float32)).unsqueeze(0)
        forecast_q, weights = model(last_window)
        forecast_q = forecast_q.squeeze(0).numpy()  # (3,) returns for p10/p50/p90
        last_weights = weights[0, -1, :].numpy()

    last_close = float(close.iloc[-1])
    q10, q50, q90 = (float(q) for q in forecast_q)

    fields = {
        "status": "ok",
        "n_observations": int(n),
        "n_train_windows": int(len(X)),
        "lookback": LOOKBACK,
        "last_close": last_close,
        "forecast_return_p10": q10,
        "forecast_return_p50": q50,
        "forecast_return_p90": q90,
        "forecast_price_p10": last_close * (1 + q10),
        "forecast_price_p50": last_close * (1 + q50),
        "forecast_price_p90": last_close * (1 + q90),
        "direction": "up" if q50 > 0 else ("down" if q50 < 0 else "flat"),
        "variable_selection_weights": {name: float(w) for name, w in zip(FEATURE_NAMES, last_weights)},
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
        fields, _model = _fit_and_forecast(bars, seed=seed)
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
