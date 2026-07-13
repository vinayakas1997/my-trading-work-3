"""Rolling std of daily returns."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators.daily_return.daily_return import compute as daily_ret
from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import rolling_std

KIND = "volatility"
DESCRIPTION = "Rolling volatility of daily returns"
PARAMS = {"period": {"type": "int", "default": 20, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("volatility_{period}d",)
EXAMPLES = ("volatility", "volatility:period=20", "volatility_20d")
LEGACY_ALIASES = {
    "volatility_20d": {"period": 20},
}

FEATURE_NAMES = ("volatility_20d",)
WARMUP_BARS = 21

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 20))
    dr = daily_ret(rows, name="daily_return")["daily_return"]
    col_name = name if match_name(_MOD, name) else f"volatility_{period}d"
    return {col_name: rolling_std(dr, period)}
