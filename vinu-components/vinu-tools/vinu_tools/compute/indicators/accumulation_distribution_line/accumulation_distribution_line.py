"""Accumulation/Distribution Line (unbounded cumulative running total --
NOT the same indicator as Chaikin Money Flow, which is a bounded rolling
oscillator built on the same money-flow-multiplier formula; see
`chaikin_money_flow/chaikin_money_flow.py`)."""

from __future__ import annotations

from vinu_tools.compute.indicators._shared.rows import col

KIND = "ad_line"
DESCRIPTION = "Accumulation/Distribution Line"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("accumulation_distribution_line",)
EXAMPLES = ("accumulation_distribution_line",)
LEGACY_ALIASES = {"accumulation_distribution_line": {}}

FEATURE_NAMES = ("accumulation_distribution_line",)
WARMUP_BARS = 1


def matches(name: str) -> bool:
    return name == "accumulation_distribution_line"


def warmup_for(name: str) -> int:
    return WARMUP_BARS


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    high, low, close, volume = col(rows, "high"), col(rows, "low"), col(rows, "close"), col(rows, "volume")
    n = len(close)
    out: list[float | None] = [None] * n
    running = 0.0
    for i in range(n):
        h, l, c, v = high[i], low[i], close[i], volume[i]
        clv = ((c - l) - (h - c)) / (h - l) if h != l else 0.0
        running += clv * v
        out[i] = running
    return {name: out}
