"""Ichimoku Cloud (Tenkan-sen, Kijun-sen, Senkou Span A/B)."""

from __future__ import annotations

import sys

from vinu_tools.compute.indicators._shared.meta_helpers import match_name, warmup_for_name
from vinu_tools.compute.indicators._shared.rows import col

KIND = "ichimoku"
DESCRIPTION = "Ichimoku Cloud (Tenkan-sen, Kijun-sen, Senkou Span A/B)"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a", "ichimoku_senkou_b")
EXAMPLES = ("ichimoku", "ichimoku_tenkan")
LEGACY_ALIASES: dict[str, dict[str, int | float]] = {}

FEATURE_NAMES = ("ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a", "ichimoku_senkou_b")
WARMUP_BARS = 52

# Standard Ichimoku convention (Goichi Hosoda's original periods).
TENKAN_PERIOD = 9
KIJUN_PERIOD = 26
SENKOU_B_PERIOD = 52

_MOD = sys.modules[__name__]


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def _midpoint_channel(high: list[float], low: list[float], period: int) -> list[float | None]:
    n = len(high)
    out: list[float | None] = [None] * n
    for i in range(period - 1, n):
        window_h = high[i - period + 1 : i + 1]
        window_l = low[i - period + 1 : i + 1]
        out[i] = (max(window_h) + min(window_l)) / 2.0
    return out


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    """Values are point-in-time at each bar, NOT forward-shifted the way
    a charted Ichimoku cloud normally displaces Senkou A/B 26 bars ahead
    -- this is a supporting-indicator snapshot at the trigger bar, not a
    chart plot, so shifting would misrepresent "the value as of now" and
    risk being mistaken for a look-ahead value if ever read without that
    context in mind."""
    high, low = col(rows, "high"), col(rows, "low")
    n = len(high)

    tenkan = _midpoint_channel(high, low, TENKAN_PERIOD)
    kijun = _midpoint_channel(high, low, KIJUN_PERIOD)
    senkou_b = _midpoint_channel(high, low, SENKOU_B_PERIOD)
    senkou_a: list[float | None] = [None] * n
    for i in range(n):
        if tenkan[i] is not None and kijun[i] is not None:
            senkou_a[i] = (tenkan[i] + kijun[i]) / 2.0

    all_cols = {
        "ichimoku_tenkan": tenkan,
        "ichimoku_kijun": kijun,
        "ichimoku_senkou_a": senkou_a,
        "ichimoku_senkou_b": senkou_b,
    }
    if name in all_cols:
        return {name: all_cols[name]}
    return all_cols
