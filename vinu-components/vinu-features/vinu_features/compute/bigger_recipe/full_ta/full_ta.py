"""All standard TA indicators."""

from __future__ import annotations

NAME = "full_ta"
DESCRIPTION = "All standard TA indicators"
WARMUP_BARS = 100
FEATURE_NAMES = (
    "sma_5", "sma_10", "sma_20", "sma_50", "sma_100",
    "ema_12", "ema_26", "rsi_14", "macd", "macd_signal",
    "daily_return", "volatility_20d", "atr_14",
    "bb_upper", "bb_mid", "bb_lower", "stoch_k", "stoch_d",
    "obv", "vwap", "volume_ratio_20", "high_low_spread",
    "open_close_return", "momentum_10", "roc_12", "cci_20",
    "williams_r_14", "adx_14", "supertrend", "cmf_20",
    "aroon_up", "aroon_down",
)


def resolve() -> tuple[str, ...]:
    return FEATURE_NAMES


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    return {}
