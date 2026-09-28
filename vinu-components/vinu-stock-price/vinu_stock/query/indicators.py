"""Technical indicators computed at query time (TASK-S01).

item #21 pattern #2 (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md), item #19 finding #3: this
module used to hand-roll SMA/RSI/MACD/volatility/ADX from scratch instead
of using `vinu-tools`' shared, tested indicator library -- the 4th
confirmed instance of the same duplication class already fixed for
Track 1 (`06-mistake-duplicated-indicator-logic.md`), vinu-screener
(item #18.4), and trend_lifecycle (item #20 finding #7). Unlike those
three, this one carried no historical-migration risk at all: these
values are computed fresh on every API call and never persisted
anywhere (confirmed -- the only DB touched here is an in-memory, per-
request DuckDB connection used to join raw prices, not to store computed
indicators), so there was no "old formula vs. new formula" seam to
manage. Delegates directly to `vinu-tools`' `compute(rows, name=...)`
functions now -- same uniform interface every module in that library
already shares, no bridging shim needed the way the pandas-`Series`-based
callers elsewhere required.
"""

from __future__ import annotations

from typing import Sequence

from vinu_tools.compute.indicators.adx.adx import compute as _adx_compute
from vinu_tools.compute.indicators.daily_return.daily_return import compute as _daily_return_compute
from vinu_tools.compute.indicators.macd.macd import compute as _macd_compute
from vinu_tools.compute.indicators.macd_signal.macd_signal import compute as _macd_signal_compute
from vinu_tools.compute.indicators.rsi.rsi import compute as _rsi_compute
from vinu_tools.compute.indicators.sma.sma import compute as _sma_compute
from vinu_tools.compute.indicators.volatility_20d.volatility_20d import compute as _volatility_compute

SUPPORTED_INDICATORS = frozenset(
    {
        "sma_5",
        "sma_10",
        "sma_20",
        "sma_50",
        "rsi_14",
        "macd",
        "macd_signal",
        "daily_return",
        "volatility_20d",
        "adx_14",
    }
)


def parse_indicator_names(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    unknown = []
    for n in names:
        if n.startswith("sma_"):
            try:
                int(n.split("_", 1)[1])
                continue
            except (ValueError, IndexError):
                pass
        if n not in SUPPORTED_INDICATORS:
            unknown.append(n)
    if unknown:
        raise ValueError(f"Unknown indicators: {', '.join(unknown)}")
    return names


def apply_indicators(rows: list[dict], names: Sequence[str]) -> list[dict]:
    if not rows or not names:
        return rows

    # vinu-tools' adx needs high/low present -- same close-fallback this
    # module already used for bars that only carry close, preserved here
    # so this swap changes only the math, not which inputs are tolerated.
    tool_rows = [
        {
            "close": float(r["close"]),
            "high": float(r["high"]) if r.get("high") is not None else float(r["close"]),
            "low": float(r["low"]) if r.get("low") is not None else float(r["close"]),
        }
        for r in rows
    ]
    out = [dict(r) for r in rows]

    for name in names:
        if name.startswith("sma_"):
            result = _sma_compute(tool_rows, name=name)
        elif name == "rsi_14":
            result = _rsi_compute(tool_rows, name=name)
        elif name == "macd":
            result = _macd_compute(tool_rows, name=name)
        elif name == "macd_signal":
            result = _macd_signal_compute(tool_rows, name=name)
        elif name == "daily_return":
            result = _daily_return_compute(tool_rows, name=name)
        elif name == "volatility_20d":
            result = _volatility_compute(tool_rows, name=name)
        elif name == "adx_14":
            result = _adx_compute(tool_rows, name=name)
        else:
            continue
        vals = result[name]
        for i, v in enumerate(vals):
            out[i][name] = v

    return out


def apply_adjusted_prices(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        rec = dict(row)
        factor = float(rec.get("adj_factor", 1.0) or 1.0)
        if factor != 1.0:
            for key in ("open", "high", "low", "close"):
                if key in rec and rec[key] is not None:
                    rec[key] = float(rec[key]) * factor
        out.append(rec)
    return out
