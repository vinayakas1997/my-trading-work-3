"""Momentum and MACD bundle."""

from __future__ import annotations

NAME = "momentum"
DESCRIPTION = "Momentum and MACD bundle"
WARMUP_BARS = 50
FEATURE_NAMES = ("sma_10", "sma_50", "rsi_14", "macd", "macd_signal")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
