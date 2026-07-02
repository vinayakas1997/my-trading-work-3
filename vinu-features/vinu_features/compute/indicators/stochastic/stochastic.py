"""Stochastic oscillator K and D."""

from __future__ import annotations

import sys

from vinu_features.compute.indicators._shared.meta_helpers import match_name, params_for_name, warmup_for_name
from vinu_features.compute.indicators._shared.rolling import sma
from vinu_features.compute.indicators._shared.rows import col

KIND = "stochastic"
DESCRIPTION = "Stochastic oscillator"
PARAMS = {
    "period": {"type": "int", "default": 14, "min": 2, "max": 500},
    "smooth": {"type": "int", "default": 3, "min": 1, "max": 50},
}
OUTPUT_COLUMNS = ("stoch_k_{period}", "stoch_d_{period}")
EXAMPLES = ("stochastic", "stochastic:period=14,smooth=3", "stoch_k")
LEGACY_ALIASES = {
    "stoch_k": {"period": 14, "smooth": 3},
    "stoch_d": {"period": 14, "smooth": 3},
}

FEATURE_NAMES = ("stoch_k", "stoch_d")
WARMUP_BARS = 17

_MOD = sys.modules[__name__]


def resolve_spec_columns(params: dict[str, int | float]) -> tuple[str, ...]:
    period = int(params.get("period", 14))
    return (f"stoch_k_{period}", f"stoch_d_{period}")


def matches(name: str) -> bool:
    return match_name(_MOD, name)


def warmup_for(name: str) -> int:
    return warmup_for_name(_MOD, name)


def compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]:
    params = params_for_name(_MOD, name)
    period = int(params.get("period", 14))
    smooth = int(params.get("smooth", 3))
    high, low, close = col(rows, "high"), col(rows, "low"), col(rows, "close")
    n = len(close)
    raw_k: list[float | None] = [None] * n
    for i in range(period - 1, n):
        hh = max(high[i - period + 1 : i + 1])
        ll = min(low[i - period + 1 : i + 1])
        if hh != ll:
            raw_k[i] = 100.0 * (close[i] - ll) / (hh - ll)
        else:
            raw_k[i] = 50.0
    k_vals = [v if v is not None else 50.0 for v in raw_k]
    d_line = sma(k_vals, smooth)
    k_name, d_name = f"stoch_k_{period}", f"stoch_d_{period}"
    legacy = {"stoch_k": raw_k, "stoch_d": d_line}
    parametric = {k_name: raw_k, d_name: d_line}
    all_cols = {**legacy, **parametric}
    if name in all_cols:
        return {name: all_cols[name]}
    return all_cols
