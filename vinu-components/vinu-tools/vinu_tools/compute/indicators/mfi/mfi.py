"""Money Flow Index."""

from __future__ import annotations

import sys

from vinu_tools.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_tools.compute.indicators._shared.rows import col

KIND = "mfi"
DESCRIPTION = "Money Flow Index"
PARAMS = {"period": {"type": "int", "default": 14, "min": 2, "max": 500}}
OUTPUT_COLUMNS = ("mfi_{period}",)
EXAMPLES = ("mfi", "mfi:period=14", "mfi_14")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("mfi_14",)
WARMUP_BARS = 15

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    period = int(params_for_name(_MOD, name).get("period", 14))
    high, low, close, volume = col(rows, "high"), col(rows, "low"), col(rows, "close"), col(rows, "volume")
    n = len(close)
    tp = [(h + l + c) / 3.0 for h, l, c in zip(high, low, close)]
    raw_mf = [t * v for t, v in zip(tp, volume)]

    out: list[float | None] = [None] * n
    for i in range(period, n):
        pos_sum = 0.0
        neg_sum = 0.0
        for j in range(i - period + 1, i + 1):
            if tp[j] > tp[j - 1]:
                pos_sum += raw_mf[j]
            elif tp[j] < tp[j - 1]:
                neg_sum += raw_mf[j]
        if neg_sum == 0:
            out[i] = 100.0
        else:
            money_ratio = pos_sum / neg_sum
            out[i] = 100.0 - (100.0 / (1.0 + money_ratio))

    col_name = name if match_name(_MOD, name) else f"mfi_{period}"
    return {col_name: out}
