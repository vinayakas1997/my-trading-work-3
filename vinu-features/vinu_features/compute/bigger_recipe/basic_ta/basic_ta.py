"""Minimal trend and momentum preset."""

from __future__ import annotations

NAME = "basic_ta"
DESCRIPTION = "Minimal trend and momentum"
WARMUP_BARS = 21
FEATURE_NAMES = ("sma_20", "rsi_14", "daily_return")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
