"""Williams %R."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rows import col

KIND = "williams_r"
DESCRIPTION = "Williams %R"
PARAMS = {"period": {"type": "int", "default": 14, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("williams_r_{period}",)
EXAMPLES = ("williams_r", "williams_r:period=14", "williams_r_14")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("williams_r_14",)
WARMUP_BARS = 15

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 14))
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    out: list[float | None] = [None] * len(close)
    for i in range(period - 1, len(close)):
        hh = max(high[i - period + 1 : i + 1])
        ll = min(low[i - period + 1 : i + 1])
        if hh != ll:
            out[i] = -100.0 * (hh - close[i]) / (hh - ll)
    col_name = name if match_name(_MOD, name) else f"williams_r_{period}"
    return {col_name: out}
