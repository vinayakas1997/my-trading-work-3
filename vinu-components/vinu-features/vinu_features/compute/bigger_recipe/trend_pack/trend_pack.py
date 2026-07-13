"""SMA/EMA/MACD/ADX trend bundle."""

from __future__ import annotations

NAME = "trend_pack"
DESCRIPTION = "SMA/EMA/MACD/ADX trend bundle"
WARMUP_BARS = 50
FEATURE_NAMES = ("sma_20", "sma_50", "ema_12", "ema_26", "macd", "macd_signal", "adx_14")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
