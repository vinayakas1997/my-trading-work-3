"""Average Directional Index."""

from __future__ import annotations

import sys

from vinu_tools.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_tools.compute.indicators._shared.rolling import true_range, wilder_smooth
from vinu_tools.compute.indicators._shared.rows import col

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
    # item #20 finding #1: real Wilder smoothing (alpha=1/period), not
    # standard EMA (alpha=2/(period+1)) -- see wilder_smooth's own
    # docstring. Unlike the old ema()-based version (which fabricated a
    # value from index 0 with no real warmup), this has a genuine None
    # warmup period, handled explicitly below rather than assumed away.
    atr_vals = wilder_smooth(tr, period)
    plus_dm_smooth = wilder_smooth(plus_dm, period)
    minus_dm_smooth = wilder_smooth(minus_dm, period)

    plus_di: list[float | None] = [None] * n
    minus_di: list[float | None] = [None] * n
    for i in range(n):
        a = atr_vals[i]
        if a is None:
            continue
        if a == 0:
            plus_di[i] = 0.0
            minus_di[i] = 0.0
            continue
        pdm, mdm = plus_dm_smooth[i], minus_dm_smooth[i]
        if pdm is not None:
            plus_di[i] = 100 * pdm / a
        if mdm is not None:
            minus_di[i] = 100 * mdm / a

    dx: list[float | None] = [None] * n
    for i in range(n):
        if plus_di[i] is None or minus_di[i] is None:
            continue
        s = plus_di[i] + minus_di[i]
        if s > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / s
        else:
            dx[i] = 0.0
    adx_raw = wilder_smooth([d if d is not None else 0.0 for d in dx], period)
    out: list[float | None] = [None] * n
    for i in range(period * 2, n):
        out[i] = adx_raw[i]
    col_name = name if match_name(_MOD, name) else f"adx_{period}"
    return {col_name: out}
