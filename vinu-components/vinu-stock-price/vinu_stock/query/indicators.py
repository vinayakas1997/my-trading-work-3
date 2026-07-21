"""Technical indicators computed at query time (TASK-S01)."""

from __future__ import annotations

from typing import Sequence

import warnings

import numpy as np

SUPPORTED_INDICATORS = frozenset(
    {
        "sma_5",
        "sma_10",
        "sma_20",
        "sma_50",
        "rsi_14",
        "macd",
        "macd_signal",
        "daily_return",
        "volatility_20d",
    }
)


def parse_indicator_names(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    unknown = []
    for n in names:
        if n.startswith("sma_"):
            try:
                int(n.split("_", 1)[1])
                continue
            except (ValueError, IndexError):
                pass
        if n not in SUPPORTED_INDICATORS:
            unknown.append(n)
    if unknown:
        raise ValueError(f"Unknown indicators: {', '.join(unknown)}")
    return names


def _nan_to_none(v: float) -> float | None:
    return None if np.isnan(v) else v


def apply_indicators(rows: list[dict], names: Sequence[str]) -> list[dict]:
    if not rows or not names:
        return rows

    closes = [float(r["close"]) for r in rows]
    out = [dict(r) for r in rows]

    for name in names:
        if name.startswith("sma_"):
            period = int(name.split("_", 1)[1])
            vals = _sma(closes, period)
            for i, v in enumerate(vals):
                out[i][name] = v
        elif name == "rsi_14":
            vals = _rsi(closes, 14)
            for i, v in enumerate(vals):
                out[i][name] = v
        elif name in ("macd", "macd_signal"):
            macd_line, signal_line = _macd(closes)
            if name == "macd":
                for i, v in enumerate(macd_line):
                    out[i]["macd"] = v
            else:
                for i, v in enumerate(signal_line):
                    out[i]["macd_signal"] = v
        elif name == "daily_return":
            vals = _daily_return(closes)
            for i, v in enumerate(vals):
                out[i][name] = v
        elif name == "volatility_20d":
            vals = _rolling_std(_daily_return(closes), 20)
            for i, v in enumerate(vals):
                out[i][name] = v

    return out


def _sma(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    if n < period or period <= 0:
        return [None] * n
    arr = np.array(values, dtype=float)
    cum = np.empty(n + 1)
    cum[0] = 0.0
    np.cumsum(arr, out=cum[1:])
    result = np.full(n, np.nan)
    result[period - 1:] = (cum[period:] - cum[:-period]) / period
    return [_nan_to_none(v) for v in result.tolist()]


def _rsi(values: list[float], period: int) -> list[float | None]:
    n = len(values)
    if n < period + 1:
        return [None] * n
    arr = np.array(values, dtype=float)
    changes = np.diff(arr)
    gains = np.where(changes > 0, changes, 0.0)
    losses = np.where(changes < 0, -changes, 0.0)

    # Wilder smoothing: EMA with alpha = 1/period
    alpha = 1.0 / period
    avg_gain = np.full(n, np.nan)
    avg_loss = np.full(n, np.nan)
    avg_gain[period] = gains[:period].mean()
    avg_loss[period] = losses[:period].mean()
    for i in range(period + 1, n):
        avg_gain[i] = avg_gain[i - 1] * (1 - alpha) + gains[i - 1] * alpha
        avg_loss[i] = avg_loss[i - 1] * (1 - alpha) + losses[i - 1] * alpha

    rs = np.where(avg_loss == 0, np.nan, avg_gain / avg_loss)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        rsi_vals = 100.0 - 100.0 / (1.0 + rs)
    result = np.where(np.isnan(rs), 100.0, rsi_vals)
    return [_nan_to_none(v) for v in result.tolist()]


def _ema(values: list[float], span: int) -> np.ndarray:
    arr = np.array(values, dtype=float)
    alpha = 2.0 / (span + 1)
    out = np.empty(len(arr))
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _macd(values: list[float]) -> tuple[list[float | None], list[float | None]]:
    n = len(values)
    if n < 34:
        return [None] * n, [None] * n
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    macd_line = ema12 - ema26
    signal_raw = _ema(macd_line.tolist(), 9)
    macd_out: list[float | None] = [None] * n
    signal_out: list[float | None] = [None] * n
    for i in range(25, n):
        macd_out[i] = macd_line[i]
    for i in range(33, n):
        signal_out[i] = signal_raw[i]
    return macd_out, signal_out


def _daily_return(values: list[float]) -> list[float | None]:
    n = len(values)
    if n < 2:
        return [None] * n
    arr = np.array(values, dtype=float)
    result = np.full(n, np.nan)
    result[1:] = (arr[1:] - arr[:-1]) / np.where(arr[:-1] == 0, np.nan, arr[:-1])
    return [_nan_to_none(v) for v in result.tolist()]


def _rolling_std(values: list[float | None], period: int) -> list[float | None]:
    n = len(values)
    if n < period:
        return [None] * n
    arr = np.array(values, dtype=float)
    result = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = arr[i - period + 1 : i + 1]
        if not np.any(np.isnan(window)):
            result[i] = np.std(window, ddof=0)
    return [_nan_to_none(v) for v in result.tolist()]


def apply_adjusted_prices(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        rec = dict(row)
        factor = float(rec.get("adj_factor", 1.0) or 1.0)
        if factor != 1.0:
            for key in ("open", "high", "low", "close"):
                if key in rec and rec[key] is not None:
                    rec[key] = float(rec[key]) * factor
        out.append(rec)
    return out
