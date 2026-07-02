"""On-Balance Volume."""

from __future__ import annotations

from vinu_features.compute.indicators._shared.rows import col

KIND = "obv"
DESCRIPTION = "On-Balance Volume"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("obv",)
EXAMPLES = ("obv",)
LEGACY_ALIASES = {"obv": {}}

FEATURE_NAMES = ("obv",)
WARMUP_BARS = 2


def matches(name: str) -> bool:
    return name == "obv"


def warmup_for(name: str) -> int:
    return 2


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    close, volume = col(rows, "close"), col(rows, "volume")
    obv: list[float | None] = [None] * len(close)
    if not close:
        return {name: obv}
    running = volume[0]
    obv[0] = running
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            running += volume[i]
        elif close[i] < close[i - 1]:
            running -= volume[i]
        obv[i] = running
    return {name: obv}
