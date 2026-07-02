"""Exponential moving average — ema_N columns."""

from __future__ import annotations

import re
import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import ema as ema_fn
from vinu_features.compute.indicators._shared.rows import col

KIND = "ema"
DESCRIPTION = "Exponential moving average"
PARAMS = {"period": {"type": "int", "default": 12, "min": 1, "max": 500}}
OUTPUT_COLUMNS = ("ema_{period}",)
EXAMPLES = ("ema:period=12", "ema:period=26", "ema_12")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

EMA_RE = re.compile(r"^ema_(\d+)$")
WARMUP_BARS = 50

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 12))
    m = EMA_RE.match(name)
    if m:
        period = int(m.group(1))
    col_name = name if match_name(_MOD, name) else f"ema_{period}"
    closes = col(rows, "close")
    return {col_name: ema_fn(closes, period)}
