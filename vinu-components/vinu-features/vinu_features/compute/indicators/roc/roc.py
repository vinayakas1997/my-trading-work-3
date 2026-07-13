"""Rate of change."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rows import col

KIND = "roc"
DESCRIPTION = "Rate of change"
PARAMS = {"period": {"type": "int", "default": 12, "min": 1, "max": 500}}
OUTPUT_COLUMNS = ("roc_{period}",)
EXAMPLES = ("roc", "roc:period=12", "roc_12")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("roc_12",)
WARMUP_BARS = 13

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 12))
    close = col(rows, "close")
    out: list[float | None] = [None] * len(close)
    for i in range(period, len(close)):
        prev = close[i - period]
        out[i] = (close[i] - prev) / prev * 100.0 if prev else None
    col_name = name if match_name(_MOD, name) else f"roc_{period}"
    return {col_name: out}
