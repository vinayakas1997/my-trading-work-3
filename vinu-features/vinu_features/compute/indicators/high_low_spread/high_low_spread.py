"""High-low spread relative to close."""

from __future__ import annotations

from vinu_features.compute.indicators._shared.rows import col

KIND = "high_low_spread"
DESCRIPTION = "High-low spread relative to close"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("high_low_spread",)
EXAMPLES = ("high_low_spread",)
LEGACY_ALIASES = {"high_low_spread": {}}

FEATURE_NAMES = ("high_low_spread",)
WARMUP_BARS = 1


def matches(name: str) -> bool:
    return name == "high_low_spread"


def warmup_for(name: str) -> int:
    return 1


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    out: list[float | None] = []
    for h, l, c in zip(high, low, close):
        out.append((h - l) / c if c else None)
    return {name: out}
