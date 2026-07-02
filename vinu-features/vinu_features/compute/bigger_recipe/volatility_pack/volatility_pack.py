"""ATR, Bollinger, volatility bundle."""

from __future__ import annotations

NAME = "volatility_pack"
DESCRIPTION = "ATR, Bollinger, volatility"
WARMUP_BARS = 21
FEATURE_NAMES = ("atr_14", "bb_upper", "bb_mid", "bb_lower", "volatility_20d")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
