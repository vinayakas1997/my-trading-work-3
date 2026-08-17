"""Decimal quantization for the real-money path (implementation-plan task 12).

The order-quantity and cash-ledger code (signal_translator, execution slicing,
book/positions.py) used raw float arithmetic: share quantities, average entry
prices, commissions and realized PnL were computed and stored as IEEE doubles,
so compounding drift (the `0.1 + 0.2 != 0.3` class) could become real lost or
gained money. This module gives that path one explicit, documented rounding
rule and nothing else -- analytics (weights, Sharpe/volatility, thresholds)
stays on float, exactly as the plan requires.

Rounding rules (both ROUND_HALF_UP, banker-safe for money):
- Quantities: rounded to the instrument's tradeable increment. Default is
  whole shares (`VINU_LIVE_SHARE_PRECISION=0`); set to N for brokers that
  support N-decimal fractional shares.
- Money (prices, average entry, commissions, realized PnL): rounded to cents
  (2 decimal places).

Storage note: the SQLite ledger columns stay REAL. Each write stores the
float nearest to an already-quantized Decimal, and every read converts back
through `Decimal(str(x))`, so the cents/share value round-trips exactly --
no schema migration, no compounding drift, no pandas/numpy interop cost on
the analytics side.
"""

from __future__ import annotations

import os
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

MONEY_PLACES = 2
MONEY_QUANTUM = Decimal("1e-2")

_SHARE_PLACES = int(os.environ.get("VINU_LIVE_SHARE_PRECISION", "0"))
SHARE_QUANTUM = Decimal("1e-%d" % _SHARE_PLACES) if _SHARE_PLACES > 0 else Decimal("1")


def to_decimal(value: float | int | str | Decimal) -> Decimal:
    """float -> Decimal via str() so 0.1 stays Decimal("0.1"), never the
    binary float artifact 0.1000000000000000055511... -- the entire point
    of the conversion."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_qty(value: float | int | str | Decimal) -> Decimal:
    return to_decimal(value).quantize(SHARE_QUANTUM, rounding=ROUND_HALF_UP)


def floor_qty(value: float | int | str | Decimal) -> Decimal:
    """Floor to the share quantum (ROUND_DOWN). Used by execution slicing:
    intermediate slices floor so the remainder folded into the final slice
    is always non-negative, keeping slice quantities summing exactly to the
    order quantity."""
    return to_decimal(value).quantize(SHARE_QUANTUM, rounding=ROUND_DOWN)


def quantize_money(value: float | int | str | Decimal) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def qty_float(value: float | int | str | Decimal) -> float:
    """Quantized share count as float for storage/return (value is exact to
    the share quantum -- the float holds cents/share exactly as a double)."""
    return float(quantize_qty(value))


def money_float(value: float | int | str | Decimal) -> float:
    return float(quantize_money(value))


def sum_money(values: list[float | int | str | Decimal]) -> float:
    """Exact Decimal sum of money values, returned as a float rounded to
    cents -- the drift-proof replacement for `float(sum(values))`."""
    total = Decimal("0")
    for v in values:
        total += quantize_money(v)
    return float(total)