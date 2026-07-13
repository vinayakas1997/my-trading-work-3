"""Commodity Channel Index."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rows import col

KIND = "cci"
DESCRIPTION = "Commodity Channel Index"
PARAMS = {"period": {"type": "int", "default": 20, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("cci_{period}",)
EXAMPLES = ("cci", "cci:period=20", "cci_20")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("cci_20",)
WARMUP_BARS = 21

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 20))
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    tp = [(h + l + c) / 3.0 for h, l, c in zip(high, low, close)]
    out: list[float | None] = [None] * len(tp)
    for i in range(period - 1, len(tp)):
        window = tp[i - period + 1 : i + 1]
        mean = sum(window) / period
        mad = sum(abs(x - mean) for x in window) / period
        if mad > 0:
            out[i] = (tp[i] - mean) / (0.015 * mad)
    col_name = name if match_name(_MOD, name) else f"cci_{period}"
    return {col_name: out}
