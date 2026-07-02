"""Volume-weighted average price (cumulative session)."""

from __future__ import annotations

from vinu_features.compute.indicators._shared.rows import col

KIND = "vwap"
DESCRIPTION = "Volume-weighted average price"
PARAMS: dict = {}
OUTPUT_COLUMNS = ("vwap",)
EXAMPLES = ("vwap",)
LEGACY_ALIASES = {"vwap": {}}

FEATURE_NAMES = ("vwap",)
WARMUP_BARS = 1


def matches(name: str) -> bool:
    return name == "vwap"


def warmup_for(name: str) -> int:
    return 1


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    high, low, close, volume = col(rows, "high"), col(rows, "low"), col(rows, "close"), col(rows, "volume")
    tp = [(h + l + c) / 3.0 for h, l, c in zip(high, low, close)]
    cum_vol = 0.0
    cum_tp_vol = 0.0
    out: list[float | None] = []
    for t, v in zip(tp, volume):
        cum_vol += v
        cum_tp_vol += t * v
        out.append(cum_tp_vol / cum_vol if cum_vol > 0 else None)
    return {name: out}
