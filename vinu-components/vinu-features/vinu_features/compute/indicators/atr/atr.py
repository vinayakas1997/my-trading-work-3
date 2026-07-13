"""Average True Range."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import sma
from vinu_features.compute.indicators._shared.rows import col

KIND = "atr"
DESCRIPTION = "Average True Range"
PARAMS = {"period": {"type": "int", "default": 14, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("atr_{period}",)
EXAMPLES = ("atr", "atr:period=20", "atr_14")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("atr_14",)
WARMUP_BARS = 15

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 14))
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    from vinu_features.compute.indicators._shared.rolling import true_range

    tr = true_range(high, low, close)
    col_name = name if match_name(_MOD, name) else f"atr_{period}"
    return {col_name: sma(tr, period)}
