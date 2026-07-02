"""Simple moving average — sma_N columns."""

from __future__ import annotations

import re
import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import sma as sma_fn
from vinu_features.compute.indicators._shared.rows import col

KIND = "sma"
DESCRIPTION = "Simple moving average"
PARAMS = {"period": {"type": "int", "default": 20, "min": 1, "max": 500}}
OUTPUT_COLUMNS = ("sma_{period}",)
EXAMPLES = ("sma:period=20", "sma:period=100", "sma_20")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

SMA_RE = re.compile(r"^sma_(\d+)$")
FEATURE_PREFIX = "sma_"
WARMUP_BARS = 100

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 20))
    m = SMA_RE.match(name)
    if m:
        period = int(m.group(1))
    col_name = name if match_name(_MOD, name) else f"sma_{period}"
    closes = col(rows, "close")
    return {col_name: sma_fn(closes, period)}
