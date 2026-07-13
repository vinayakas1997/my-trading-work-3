"""Average Directional Index."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import ema, true_range
from vinu_features.compute.indicators._shared.rows import col

KIND = "adx"
DESCRIPTION = "Average Directional Index"
PARAMS = {"period": {"type": "int", "default": 14, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("adx_{period}",)
EXAMPLES = ("adx", "adx:period=14", "adx_14")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("adx_14",)
WARMUP_BARS = 28

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 14))
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    n = len(close)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
    tr = true_range(high, low, close)
    atr_vals = ema(tr, period)
    plus_di = [
        0.0 if atr_vals[i] == 0 else 100 * ema(plus_dm, period)[i] / atr_vals[i] for i in range(n)
    ]
    minus_di = [
        0.0 if atr_vals[i] == 0 else 100 * ema(minus_dm, period)[i] / atr_vals[i] for i in range(n)
    ]
    dx: list[float | None] = [None] * n
    for i in range(n):
        s = plus_di[i] + minus_di[i]
        if s > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / s
    adx_raw = ema([d if d is not None else 0.0 for d in dx], period)
    out: list[float | None] = [None] * n
    for i in range(period * 2, n):
        out[i] = adx_raw[i]
    col_name = name if match_name(_MOD, name) else f"adx_{period}"
    return {col_name: out}
