"""Shared rolling math for indicator modules."""

from __future__ import annotations

import math


def sma(values: list[float], period: int) -> list[float | None]:
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


def ema(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (span + 1)
    out: list[float] = []
    ema_val = values[0]
    for v in values:
        ema_val = alpha * v + (1 - alpha) * ema_val
        out.append(ema_val)
    return out


def rolling_std(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for i in range(period, len(values)):
        window = [v for v in values[i - period + 1 : i + 1] if v is not None]
        if len(window) < period:
            continue
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        result[i] = math.sqrt(var)
    return result


def true_range(high: list[float], low: list[float], close: list[float]) -> list[float]:
    tr: list[float] = [high[0] - low[0]] if high else []
    for i in range(1, len(high)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return tr
