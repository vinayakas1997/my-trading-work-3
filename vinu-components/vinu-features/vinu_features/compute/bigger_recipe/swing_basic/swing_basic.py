"""Swing trading preset."""

from __future__ import annotations

NAME = "swing_basic"
DESCRIPTION = "Swing trading preset"
WARMUP_BARS = 100
FEATURE_NAMES = ("sma_20", "sma_100", "rsi_14", "volatility_20d")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
