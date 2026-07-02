"""MACD line (EMA12 - EMA26)."""

from __future__ import annotations

from vinu_features.compute.indicators._shared.rolling import ema
from vinu_features.compute.indicators._shared.rows import col

KIND = "macd"
DESCRIPTION = "MACD line"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("macd",)
EXAMPLES = ("macd",)
LEGACY_ALIASES = {"macd": {}}

FEATURE_NAMES = ("macd",)
WARMUP_BARS = 34


def matches(name: str) -> bool:
    return name == "macd"


def warmup_for(name: str) -> int:
    return 34


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    closes = col(rows, "close")
    macd_line, _ = _macd(closes)
    return {name: macd_line}


def _macd(values: list[float]) -> tuple[list[float | None], list[float | None]]:
    if not values:
        return [], []
    ema12 = ema(values, 12)
    ema26 = ema(values, 26)
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal_raw = ema(macd_line, 9)
    macd_out: list[float | None] = [None] * len(values)
    signal_out: list[float | None] = [None] * len(values)
    for i in range(25, len(values)):
        macd_out[i] = macd_line[i]
    for i in range(33, len(values)):
        signal_out[i] = signal_raw[i]
    return macd_out, signal_out
