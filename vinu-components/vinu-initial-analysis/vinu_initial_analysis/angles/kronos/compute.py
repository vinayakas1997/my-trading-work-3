"""Kronos — the flagship financial K-line foundation model (AAAI 2026).

See ../../../New-talk-/Final-implementation/01-present-considerations/09-kronos.md
(method 9 of the 32-method plan): a specialized tokenizer discretizes
OHLCVA into hierarchical tokens, then an autoregressive decoder-only
transformer predicts the next K-line — pretrained on 12B K-line records
from 45 exchanges, published on HuggingFace by NeoQuasar
(Kronos-mini 4M -> Kronos-large 499M params).

**Backend: real pretrained weights, actually used.** The weights and the
tokenizer are pulled into the shared models dir (`vinu-infra/models.py` —
`{VINU_MODELS_DIR or data/models}/kronos` + `kronos-tokenizer`, downloaded
via `make models` / `vinu-models` and mounted read-only at serve time). The
model code itself is vendored from github.com/shiyu-coder/Kronos (MIT
License) into `_kronos_model/` (module.py, kronos.py, __init__.py) since
Kronos has no PyPI package and no pip-installable repo — vendoring lets the
weights load from disk without cloning the repo at runtime. If the local
weights are missing they are auto-downloaded via `ensure_model`; if the
fetch or the load is unavailable at runtime, this falls back to a small
in-process-trained MLP proxy over next-K-line regression (fit fresh from the
ticker's own bars, no zero-shot cross-market generalization) rather than
failing the whole angle — that path sets `model_backend: "fallback_proxy"`
and `fallback_reason` so callers can tell the two apart.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

ANGLE_NAME = "kronos"
MIN_OBSERVATIONS = 30
CONTEXT_WINDOW = 32
HORIZON = 5
FALLBACK_REASON = (
    "Kronos weights unavailable at runtime (missing download or vendored "
    "model code failed to load); using an in-process-trained small PyTorch "
    "MLP proxy over next-K-line regression instead of the real pretrained model."
)

_PREDICTOR_CACHE: dict[str, Any] = {}


class _NextBarMLP:
    """Tiny 1-hidden-layer MLP: last CONTEXT_WINDOW log-returns of OHLC ->
    next-bar log-return prediction for O/H/L/C. Trained fresh per call on
    the ticker's own history — the fallback when real weights can't load."""

    def __init__(self, n_features: int, hidden: int = 8):
        import torch

        self.torch = torch
        self.net = torch.nn.Sequential(
            torch.nn.Linear(n_features, hidden),
            torch.nn.Tanh(),
            torch.nn.Linear(hidden, 4),  # predict next O,H,L,C log-return
        )

    def fit_predict(self, X: "np.ndarray", y: "np.ndarray", x_last: "np.ndarray") -> np.ndarray:
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
    """ohlc: (n, 4) log-returns of O,H,L,C. Returns (X, y, x_last) where X
    is flattened trailing windows and y is the next-bar 4-vector target."""
    n = len(ohlc)
    xs, ys = [], []
    for i in range(window, n):
        xs.append(ohlc[i - window:i].flatten())
        ys.append(ohlc[i])
    X = np.array(xs)
    y = np.array(ys)
    x_last = ohlc[n - window:n].flatten()
    return X, y, x_last


def _model_paths() -> tuple[str, str]:
    from vinu_infra.models import ensure_model

    model_dir = ensure_model("kronos", quiet=True)
    tokenizer_dir = ensure_model("kronos-tokenizer", quiet=True)
    return str(model_dir), str(tokenizer_dir)


def _get_predictor():
    """Lazily load and cache KronosPredictor across calls in-process."""
    if ANGLE_NAME in _PREDICTOR_CACHE:
        return _PREDICTOR_CACHE[ANGLE_NAME]

    from vinu_initial_analysis.angles.kronos._kronos_model import (
        Kronos,
        KronosPredictor,
        KronosTokenizer,
    )

    model_dir, tokenizer_dir = _model_paths()
    tokenizer = KronosTokenizer.from_pretrained(tokenizer_dir)
    model = Kronos.from_pretrained(model_dir)
    predictor = KronosPredictor(model, tokenizer, max_context=512)
    _PREDICTOR_CACHE[ANGLE_NAME] = predictor
    return predictor


def _fallback_forecast(ohlc_raw: np.ndarray) -> dict[str, Any]:
    """MLP over next-K-line regression — used only if real weights can't load."""
    prev_close = np.roll(ohlc_raw[:, 3], 1)
    prev_close[0] = ohlc_raw[0, 3]
    log_returns = np.log(np.clip(ohlc_raw, 1e-8, None)) - np.log(
        np.clip(prev_close, 1e-8, None)
    )[:, None]
    X, y, x_last = _build_windows(log_returns, CONTEXT_WINDOW)
    model = _NextBarMLP(n_features=X.shape[1])
    next_bar_log_ret = model.fit_predict(X, y, x_last)
    last_close = float(ohlc_raw[-1, 3])
    return {
        "predicted_next_open": float(last_close * np.exp(next_bar_log_ret[0])),
        "predicted_next_high": float(last_close * np.exp(next_bar_log_ret[1])),
        "predicted_next_low": float(last_close * np.exp(next_bar_log_ret[2])),
        "predicted_next_close": float(last_close * np.exp(next_bar_log_ret[3])),
    }


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
    if not required_cols.issubset(bars.columns):
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(bars)),
        }])

    ohlc_raw = bars[["open", "high", "low", "close"]].astype(float).values
    if len(ohlc_raw) < MIN_OBSERVATIONS + CONTEXT_WINDOW:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(ohlc_raw)),
        }])

    model_backend = "pretrained"
    fallback_reason = None

    try:
        import torch

        predictor = _get_predictor()
        df = bars[["open", "high", "low", "close"]].astype(float)
        if "volume" in bars.columns:
            df["volume"] = bars["volume"].astype(float)
        else:
            df["volume"] = 0.0
        df["amount"] = df["volume"] * df[["open", "high", "low", "close"]].mean(axis=1)

        x_index = bars.index if isinstance(bars.index, pd.DatetimeIndex) else pd.RangeIndex(len(bars))
        if isinstance(x_index, pd.RangeIndex):
            x_ts = pd.Series(pd.to_datetime(x_index.to_series(), unit="D"))
        else:
            x_ts = pd.Series(x_index)

        # Forecast timestamps: extend from the last bar's time by the median gap.
        if isinstance(x_index, pd.DatetimeIndex) and len(x_index) >= 2:
            gap = pd.Series(x_index).diff().dropna().median()
            last_t = x_index[-1]
            y_ts = pd.Series(pd.date_range(last_t + gap, periods=HORIZON, freq=gap))
        else:
            y_ts = pd.Series(pd.date_range("2024-01-01", periods=HORIZON, freq="D"))

        with torch.no_grad():
            pred_df = predictor.predict(
                df=df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=HORIZON,
                T=0.8, top_k=0, top_p=0.9, sample_count=3, verbose=False,
            )

        next_bar = pred_df.iloc[0]
        forecast = {
            "predicted_next_open": float(next_bar["open"]),
            "predicted_next_high": float(next_bar["high"]),
            "predicted_next_low": float(next_bar["low"]),
            "predicted_next_close": float(next_bar["close"]),
            "forecast_horizon": int(len(pred_df)),
            "forecast_ohlc": {
                "open": [float(v) for v in pred_df["open"].tolist()],
                "high": [float(v) for v in pred_df["high"].tolist()],
                "low": [float(v) for v in pred_df["low"].tolist()],
                "close": [float(v) for v in pred_df["close"].tolist()],
            },
        }
        result: dict[str, Any] = {
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "ok",
            "n_observations": int(len(ohlc_raw)),
            "model_backend": model_backend,
            "checkpoint": "NeoQuasar/Kronos-base",
            "fallback_reason": fallback_reason,
            "context_window": 512,
            "last_close": float(ohlc_raw[-1, 3]),
            **forecast,
        }
    except Exception as exc:  # pragma: no cover - only hit if pkg/network unavailable
        fallback = _fallback_forecast(ohlc_raw)
        result = {
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "ok",
            "n_observations": int(len(ohlc_raw)),
            "model_backend": "fallback_proxy",
            "fallback_reason": f"{FALLBACK_REASON} Detail: {exc!r}",
            "context_window": CONTEXT_WINDOW,
            "last_close": float(ohlc_raw[-1, 3]),
            **fallback,
        }
    return pd.DataFrame([result])
