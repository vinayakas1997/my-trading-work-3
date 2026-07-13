"""Supertrend indicator (ATR-based, period 10, mult 3)."""

from __future__ import annotations

from vinu_features.compute.indicators.atr.atr import compute as atr_compute
from vinu_features.compute.indicators._shared.rows import col

KIND = "supertrend"
DESCRIPTION = "Supertrend (ATR-based)"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("supertrend",)
EXAMPLES = ("supertrend",)
LEGACY_ALIASES = {"supertrend": {}}

FEATURE_NAMES = ("supertrend",)
WARMUP_BARS = 15
MULT = 3.0


def matches(name: str) -> bool:
    return name == "supertrend"


def warmup_for(name: str) -> int:
    return 15


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    atr_vals = atr_compute(rows, name="atr_14")["atr_14"]
    n = len(close)
    hl2 = [(h + l) / 2.0 for h, l in zip(high, low)]
    upper = [hl2[i] + MULT * (atr_vals[i] or 0) for i in range(n)]
    lower = [hl2[i] - MULT * (atr_vals[i] or 0) for i in range(n)]
    st: list[float | None] = [None] * n
    direction = 1
    for i in range(1, n):
        if close[i] > upper[i - 1]:
            direction = 1
        elif close[i] < lower[i - 1]:
            direction = -1
        st[i] = lower[i] if direction == 1 else upper[i]
    return {name: st}
