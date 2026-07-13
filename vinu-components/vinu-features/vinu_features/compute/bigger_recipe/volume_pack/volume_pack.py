"""OBV, volume ratio, CMF bundle."""

from __future__ import annotations

NAME = "volume_pack"
DESCRIPTION = "OBV, volume ratio, CMF"
WARMUP_BARS = 21
FEATURE_NAMES = ("obv", "volume_ratio_20", "cmf_20")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
