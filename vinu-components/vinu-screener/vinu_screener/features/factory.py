"""Stage B (B5): `IndicatorFactory` broadcasting — VectorBT's pattern of
"one calc function + declared inputs/params, applied across every column"
(VectorBT itself broadcasts across a wide DataFrame's columns; here the
"columns" are the ~8000 symbols in the universe, each with its own OHLCV
frame rather than one shared column, so broadcasting means "call once per
symbol, sharing the same FeatureLibrary cache").

This is the thin layer B6's scan loop actually calls: give it one
indicator name + params and the whole universe (`{symbol: ohlcv_df}`), get
back `{symbol: result}` for every symbol that has the column(s) that
indicator needs — a symbol missing a required OHLCV column (a data-quality
gap, not a code bug) is silently skipped from the result dict rather than
raising, since a partial universe result is exactly what a scanner should
tolerate at ~8000-symbol scale.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .library import FeatureLibrary


class IndicatorFactory:
    def __init__(self, library: FeatureLibrary | None = None) -> None:
        self.library = library or FeatureLibrary()

    def broadcast(
        self,
        indicator: str,
        universe: dict[str, pd.DataFrame],
        params: dict[str, Any] | None = None,
    ) -> dict[str, "pd.Series | pd.DataFrame"]:
        """Compute `indicator(params)` for every symbol in `universe`.
        Skips (not raises) a symbol whose frame is missing a required
        column, or whose data errors out for indicator-specific reasons
        (e.g. too little history for `.rolling()` to produce anything —
        that just yields an all-NaN Series, not an exception, but a
        malformed frame might)."""
        out: dict[str, "pd.Series | pd.DataFrame"] = {}
        for symbol, ohlcv in universe.items():
            try:
                out[symbol] = self.library.compute(symbol, ohlcv, indicator, params)
            except KeyError:
                continue
        return out

    def latest(
        self,
        indicator: str,
        universe: dict[str, pd.DataFrame],
        params: dict[str, Any] | None = None,
        *,
        field: str = "value",
        offset: int = 0,
    ) -> dict[str, float]:
        """Convenience for the scan loop's common case: one number per
        symbol — the indicator's value `offset` bars ago, as a plain float
        (NaN dropped from the result rather than passed through, matching
        `guards.is_finite_operand`'s "not safe to act on" contract)."""
        results = self.broadcast(indicator, universe, params)
        out: dict[str, float] = {}
        for symbol, result in results.items():
            series = self.library.field(result, field)
            if offset >= len(series):
                continue
            val = series.iloc[-1 - offset]
            if pd.notna(val):
                out[symbol] = float(val)
        return out
