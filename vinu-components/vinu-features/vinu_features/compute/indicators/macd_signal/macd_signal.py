"""MACD signal line (9-period EMA of MACD)."""

from __future__ import annotations

from vinu_features.compute.indicators.macd.macd import _macd
from vinu_features.compute.indicators._shared.rows import col

KIND = "macd_signal"
DESCRIPTION = "MACD signal line"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("macd_signal",)
EXAMPLES = ("macd_signal",)
LEGACY_ALIASES = {"macd_signal": {}}

FEATURE_NAMES = ("macd_signal",)
WARMUP_BARS = 34


def matches(name: str) -> bool:
    return name == "macd_signal"


def warmup_for(name: str) -> int:
    return 34


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    closes = col(rows, "close")
    _, signal_line = _macd(closes)
    return {name: signal_line}
