"""Chaikin Money Flow."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rows import col

KIND = "cmf"
DESCRIPTION = "Chaikin Money Flow"
PARAMS = {"period": {"type": "int", "default": 20, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("cmf_{period}",)
EXAMPLES = ("cmf", "cmf:period=20", "cmf_20")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("cmf_20",)
WARMUP_BARS = 21

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 20))
    high, low, close, volume = col(rows, "high"), col(rows, "low"), col(rows, "close"), col(rows, "volume")
    mfm = []
    for h, l, c in zip(high, low, close):
        if h != l:
            mfm.append(((c - l) - (h - c)) / (h - l))
        else:
            mfm.append(0.0)
    mfv = [m * v for m, v in zip(mfm, volume)]
    out: list[float | None] = [None] * len(close)
    for i in range(period - 1, len(close)):
        vol_sum = sum(volume[i - period + 1 : i + 1])
        if vol_sum > 0:
            out[i] = sum(mfv[i - period + 1 : i + 1]) / vol_sum
    col_name = name if match_name(_MOD, name) else f"cmf_{period}"
    return {col_name: out}
