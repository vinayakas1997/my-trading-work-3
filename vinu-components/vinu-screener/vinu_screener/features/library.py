"""Stage B (B4): the shared, cached feature library the condition
evaluator's `indicator`/`compare_indicator` lookups resolve against.

Each entry is a small, declarative `IndicatorSpec` — a name, the OHLCV
input column(s) it needs, the operator(s) from `operators.py` it's built
from, and its output field name(s) (most indicators are single-output and
use the schema's default `field="value"`; a few, like MACD, expose more
than one and a leaf picks which one via `field`/`compare_field`).

Caching (`FeatureLibrary.compute`) is keyed by `(symbol, indicator, frozen
params)` and is **per scan cycle** — call `clear_cache()` once at the start
of each cycle (the scan loop, B6, owns that), not per-symbol or per-rule.
Within one cycle, ten different rules all referencing `sma(period=20)` on
the same symbol computes it once, not ten times — the actual point of
"shared" in this item's name; "cached" is what makes that sharing free
instead of a second bookkeeping cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from . import operators as op


@dataclass(frozen=True)
class IndicatorSpec:
    name: str
    inputs: tuple[str, ...]                              # OHLCV columns required, e.g. ("close",)
    compute: Callable[..., "pd.Series | pd.DataFrame"]   # (*input_series, **params) -> result
    outputs: tuple[str, ...] = ("value",)                 # field names a leaf's `field`/`compare_field` may select


def _single(series_fn: Callable[..., pd.Series]) -> Callable[..., pd.Series]:
    return series_fn


DEFAULT_REGISTRY: dict[str, IndicatorSpec] = {
    "close": IndicatorSpec("close", ("close",), lambda s: s),
    "open": IndicatorSpec("open", ("open",), lambda s: s),
    "high": IndicatorSpec("high", ("high",), lambda s: s),
    "low": IndicatorSpec("low", ("low",), lambda s: s),
    "volume": IndicatorSpec("volume", ("volume",), lambda s: s),
    "dollar_volume": IndicatorSpec("dollar_volume", ("close", "volume"), lambda c, v: c * v),
    "pct_change": IndicatorSpec("pct_change", ("close",), op.pct_change),
    "sma": IndicatorSpec("sma", ("close",), op.sma),
    "ema": IndicatorSpec("ema", ("close",), op.ema),
    "wma": IndicatorSpec("wma", ("close",), op.wma),
    "std": IndicatorSpec("std", ("close",), op.rolling_std),
    "rank": IndicatorSpec("rank", ("close",), op.rolling_rank),
    "slope": IndicatorSpec("slope", ("close",), op.slope),
    "rsi": IndicatorSpec("rsi", ("close",), op.rsi),
    "macd": IndicatorSpec("macd", ("close",), op.macd, outputs=("macd", "signal", "hist")),
}


class UnknownIndicatorError(KeyError):
    pass


class FeatureLibrary:
    def __init__(self, registry: dict[str, IndicatorSpec] | None = None) -> None:
        self._registry = dict(registry) if registry is not None else dict(DEFAULT_REGISTRY)
        self._cache: dict[tuple, "pd.Series | pd.DataFrame"] = {}

    def register(self, spec: IndicatorSpec) -> None:
        """Add or override an indicator. Call at startup, before any
        `compute()` — same convention as `RuntimeSettings.register()`."""
        self._registry[spec.name] = spec

    def spec(self, name: str) -> IndicatorSpec:
        try:
            return self._registry[name]
        except KeyError:
            raise UnknownIndicatorError(
                f"unknown indicator {name!r}; registered: {sorted(self._registry)}"
            ) from None

    def clear_cache(self) -> None:
        """Call once per scan cycle (B6 owns the cycle boundary)."""
        self._cache.clear()

    @staticmethod
    def _freeze(params: dict[str, Any]) -> tuple:
        return tuple(sorted(params.items()))

    def compute(self, symbol: str, ohlcv: pd.DataFrame, indicator: str, params: dict[str, Any] | None = None):
        """Compute (or return the cached) result of `indicator(params)` for
        `symbol`'s OHLCV frame. Returns a `pd.Series` for a single-output
        indicator or a `pd.DataFrame` for a multi-output one (columns named
        by `spec.outputs`)."""
        params = params or {}
        spec = self.spec(indicator)
        key = (symbol, indicator, self._freeze(params))
        if key in self._cache:
            return self._cache[key]
        missing = [c for c in spec.inputs if c not in ohlcv.columns]
        if missing:
            raise KeyError(f"indicator {indicator!r} needs OHLCV column(s) {missing}, not present")
        inputs = [ohlcv[c] for c in spec.inputs]
        result = spec.compute(*inputs, **params)
        self._cache[key] = result
        return result

    def field(self, result, field_name: str) -> pd.Series:
        """Select one output column from a `compute()` result — a
        single-output indicator's Series is returned as-is regardless of
        `field_name` (the schema's default `field="value"` shouldn't force
        every 1-output indicator's rule JSON to omit the key correctly);
        a multi-output DataFrame requires a real column name."""
        if isinstance(result, pd.Series):
            return result
        if field_name not in result.columns:
            raise KeyError(f"field {field_name!r} not in indicator outputs {list(result.columns)}")
        return result[field_name]
