"""Volume vs N-bar average volume."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import sma
from vinu_features.compute.indicators._shared.rows import col

KIND = "volume_ratio"
DESCRIPTION = "Volume vs moving average volume"
PARAMS = {"period": {"type": "int", "default": 20, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("volume_ratio_{period}",)
EXAMPLES = ("volume_ratio", "volume_ratio:period=20", "volume_ratio_20")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("volume_ratio_20",)
WARMUP_BARS = 21

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 20))
    volume = col(rows, "volume")
    avg = sma(volume, period)
    out: list[float | None] = [None] * len(volume)
    for i, (v, a) in enumerate(zip(volume, avg)):
        if a and a > 0:
            out[i] = v / a
    col_name = name if match_name(_MOD, name) else f"volume_ratio_{period}"
    return {col_name: out}
