"""Technical indicators computed at query time (TASK-S01)."""

from __future__ import annotations

import math
from typing import Sequence

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
    unknown = [n for n in names if n not in SUPPORTED_INDICATORS]
    if unknown:
        raise ValueError(f"Unknown indicators: {', '.join(unknown)}")
    return names


def apply_indicators(rows: list[dict], names: Sequence[str]) -> list[dict]:
    if not rows or not names:
        return rows

    closes = [float(r["close"]) for r in rows]
    n = len(closes)
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
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    window_sum = 0.0
    for i, v in enumerate(values):
        window_sum += v
        if i >= period:
            window_sum -= values[i - period]
        if i >= period - 1:
            result[i] = window_sum / period
    return result


def _rsi(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if len(values) < period + 1:
        return result
    gains = [0.0] * len(values)
    losses = [0.0] * len(values)
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains[i] = max(delta, 0.0)
        losses[i] = max(-delta, 0.0)
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    for i in range(period, len(values)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def _ema(values: list[float], span: int) -> list[float]:
    alpha = 2.0 / (span + 1)
    out: list[float] = []
    ema = values[0]
    for v in values:
        ema = alpha * v + (1 - alpha) * ema
        out.append(ema)
    return out


def _macd(values: list[float]) -> tuple[list[float | None], list[float | None]]:
    if not values:
        return [], []
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal_raw = _ema(macd_line, 9)
    macd_out: list[float | None] = [None] * len(values)
    signal_out: list[float | None] = [None] * len(values)
    for i in range(25, len(values)):
        macd_out[i] = macd_line[i]
    for i in range(33, len(values)):
        signal_out[i] = signal_raw[i]
    return macd_out, signal_out


def _daily_return(values: list[float]) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for i in range(1, len(values)):
        prev = values[i - 1]
        if prev == 0:
            result[i] = None
        else:
            result[i] = (values[i] - prev) / prev
    return result


def _rolling_std(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for i in range(period, len(values)):
        window = [v for v in values[i - period + 1 : i + 1] if v is not None]
        if len(window) < period:
            continue
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        result[i] = math.sqrt(var)
    return result


def apply_adjusted_prices(rows: list[dict]) -> list[dict]:
    """Scale OHLC by adj_factor when present (TASK-S02)."""
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
