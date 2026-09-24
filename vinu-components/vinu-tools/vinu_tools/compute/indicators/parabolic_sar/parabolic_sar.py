"""Parabolic SAR (stop-and-reverse trend indicator, Wilder's original)."""

from __future__ import annotations

from vinu_tools.compute.indicators._shared.rows import col

KIND = "parabolic_sar"
DESCRIPTION = "Parabolic SAR (stop-and-reverse trend indicator)"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("parabolic_sar",)
EXAMPLES = ("parabolic_sar",)
LEGACY_ALIASES = {"parabolic_sar": {}}

FEATURE_NAMES = ("parabolic_sar",)
WARMUP_BARS = 2

AF_START = 0.02
AF_STEP = 0.02
AF_MAX = 0.2


def matches(name: str) -> bool:
    return name == "parabolic_sar"


def warmup_for(name: str) -> int:
    return WARMUP_BARS


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    n = len(close)
    out: list[float | None] = [None] * n
    if n < 2:
        return {name: out}

    # Seed trend direction from the first two closes -- there's no prior
    # bar to derive it from otherwise.
    uptrend = close[1] >= close[0]
    sar = low[0] if uptrend else high[0]
    ep = high[1] if uptrend else low[1]
    af = AF_START
    out[1] = sar

    for i in range(2, n):
        sar = sar + af * (ep - sar)

        if uptrend:
            sar = min(sar, low[i - 1], low[i - 2])
            if low[i] < sar:
                uptrend = False
                sar = ep
                ep = low[i]
                af = AF_START
            elif high[i] > ep:
                ep = high[i]
                af = min(af + AF_STEP, AF_MAX)
        else:
            sar = max(sar, high[i - 1], high[i - 2])
            if high[i] > sar:
                uptrend = True
                sar = ep
                ep = high[i]
                af = AF_START
            elif low[i] < ep:
                ep = low[i]
                af = min(af + AF_STEP, AF_MAX)

        out[i] = sar

    return {name: out}
