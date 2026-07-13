"""Bollinger Bands."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import rolling_std, sma
from vinu_features.compute.indicators._shared.rows import col

KIND = "bollinger"
DESCRIPTION = "Bollinger Bands"
PARAMS = {
    "period": {"type": "int", "default": 20, "min": 2, "max": 500},
    "std": {"type": "float", "default": 2.0, "min": 0.1, "max": 10.0},
}
OUTPUT_COLUMNS = ("bb_upper_{period}", "bb_mid_{period}", "bb_lower_{period}")
EXAMPLES = ("bollinger", "bollinger:period=20,std=2", "bb_upper")
LEGACY_ALIASES = {
    "bb_upper": {"period": 20, "std": 2.0},
    "bb_mid": {"period": 20, "std": 2.0},
    "bb_lower": {"period": 20, "std": 2.0},
}

FEATURE_NAMES = ("bb_upper", "bb_mid", "bb_lower")
WARMUP_BARS = 21

_MOD = sys.modules[__name__]


def resolve_spec_columns(params: dict[str, int | float]) -> tuple[str, ...]:
    period = int(params.get("period", 20))
    return (f"bb_upper_{period}", f"bb_mid_{period}", f"bb_lower_{period}")


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def _band_columns(period: int) -> tuple[str, str, str]:
    return (f"bb_upper_{period}", f"bb_mid_{period}", f"bb_lower_{period}")


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    params = params_for_name(_MOD, name)
    period = int(params.get("period", 20))
    std_mult = float(params.get("std", 2.0))
    closes = col(rows, "close")
    mid = sma(closes, period)
    std = rolling_std([m if m is not None else 0.0 for m in mid], period)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if mid[i] is not None and std[i] is not None:
            upper[i] = mid[i] + std_mult * std[i]
            lower[i] = mid[i] - std_mult * std[i]

    up_name, mid_name, low_name = _band_columns(period)
    legacy = {"bb_upper": upper, "bb_mid": mid, "bb_lower": lower}
    parametric = {up_name: upper, mid_name: mid, low_name: lower}
    all_cols = {**legacy, **parametric}
    if name in all_cols:
        return {name: all_cols[name]}
    return all_cols
