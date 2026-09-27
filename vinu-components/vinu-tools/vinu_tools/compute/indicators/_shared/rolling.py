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


def wilder_smooth(values: list[float], period: int) -> list[float | None]:
    """Wilder's smoothing (RMA), alpha=1/period -- the real method Wilder-
    family indicators (RSI, ADX, ATR) are defined with, distinct from both
    plain SMA (no memory of prior bars past the window) and standard EMA
    (alpha=2/(span+1), decays roughly twice as fast for the same period).

    item #20 findings #1/#2 (system-wide-audit-and-design/
    02-open-questions-strategy-and-simulation.md): `adx.py` used to smooth
    via `ema()` and `atr.py` via `sma()` -- two different, both-wrong
    conventions for what should be the same Wilder-family math `rsi.py`'s
    own `_rsi()` already implements correctly. Extracted here verbatim
    from that already-correct recursion (`avg = (avg * (period - 1) +
    new_value) / period`, seeded by a plain average of the first `period`
    values) rather than re-derived, so all three indicators now share one
    real implementation instead of three independent, silently-different
    ones.

    Returns `None` for every index before the seed (index `period - 1`)
    is available -- unlike `ema()` above, which fabricates a value from
    index 0 with no real warmup at all.
    """
    n = len(values)
    result: list[float | None] = [None] * n
    if period <= 0 or n < period:
        return result
    avg = sum(values[:period]) / period
    result[period - 1] = avg
    for i in range(period, n):
        avg = (avg * (period - 1) + values[i]) / period
        result[i] = avg
    return result


def rolling_std(values: list[float | None], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    if period <= 0:
        return result
    window: list[float] = []
    for i, v in enumerate(values):
        if v is not None:
            window.append(v)
        else:
            window.clear()
            continue
        if len(window) > period:
            window.pop(0)
        if len(window) == period:
            mean = sum(window) / period
            var = sum((x - mean) ** 2 for x in window) / period
            result[i] = math.sqrt(var)
    return result


def true_range(high: list[float], low: list[float], close: list[float]) -> list[float]:
    tr: list[float] = [high[0] - low[0]] if high else []
    for i in range(1, len(high)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return tr
