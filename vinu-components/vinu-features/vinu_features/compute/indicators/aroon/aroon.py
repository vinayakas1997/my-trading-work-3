"""Aroon up and down."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rows import col

KIND = "aroon"
DESCRIPTION = "Aroon up and down"
PARAMS = {"period": {"type": "int", "default": 25, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("aroon_up", "aroon_down")
EXAMPLES = ("aroon", "aroon:period=25", "aroon_up")
LEGACY_ALIASES = {
    "aroon_up": {"period": 25},
    "aroon_down": {"period": 25},
}

FEATURE_NAMES = ("aroon_up", "aroon_down")
WARMUP_BARS = 26

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 25))
    high, low = col(rows, "high"), col(rows, "low")
    n = len(high)
    up: list[float | None] = [None] * n
    down: list[float | None] = [None] * n
    for i in range(period, n):
        window_h = high[i - period : i + 1]
        window_l = low[i - period : i + 1]
        days_since_high = period - window_h.index(max(window_h))
        days_since_low = period - window_l.index(min(window_l))
        up[i] = 100.0 * (period - days_since_high) / period
        down[i] = 100.0 * (period - days_since_low) / period
    all_cols = {"aroon_up": up, "aroon_down": down}
    if name in all_cols:
        return {name: all_cols[name]}
    return all_cols
