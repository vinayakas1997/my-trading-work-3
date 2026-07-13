"""Bar-over-bar close return."""

from __future__ import annotations

from vinu_features.compute.indicators._shared.rows import col

KIND = "daily_return"
DESCRIPTION = "Bar-over-bar close return"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("daily_return",)
EXAMPLES = ("daily_return",)
LEGACY_ALIASES = {"daily_return": {}}

FEATURE_NAMES = ("daily_return",)
WARMUP_BARS = 2


def matches(name: str) -> bool:
    return name == "daily_return"


def warmup_for(name: str) -> int:
    return 2


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    closes = col(rows, "close")
    result: list[float | None] = [None] * len(closes)
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        result[i] = None if prev == 0 else (closes[i] - prev) / prev
    return {name: result}
