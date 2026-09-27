"""Average True Range."""

from __future__ import annotations

import sys

from vinu_tools.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_tools.compute.indicators._shared.rolling import true_range, wilder_smooth
from vinu_tools.compute.indicators._shared.rows import col

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
    tr = true_range(high, low, close)
    col_name = name if match_name(_MOD, name) else f"atr_{period}"
    # item #20 finding #2: real (Wilder-smoothed) ATR, not a plain SMA of
    # true range -- see wilder_smooth's own docstring. Directly relevant
    # to Decision 14 (Track 2's 2xATR(14) move-detection floor,
    # ../how-to-use-29th-angle/03-move-detection-threshold-options.md):
    # this is the ATR that "2xATR" is normally understood to mean.
    return {col_name: wilder_smooth(tr, period)}
