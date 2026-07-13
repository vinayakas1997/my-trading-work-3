"""RSI, Bollinger, stochastic mean-reversion bundle."""

from __future__ import annotations

NAME = "mean_reversion_pack"
DESCRIPTION = "RSI, Bollinger, stochastic"
WARMUP_BARS = 21
FEATURE_NAMES = ("rsi_14", "bb_upper", "bb_mid", "bb_lower", "stoch_k", "stoch_d")


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
