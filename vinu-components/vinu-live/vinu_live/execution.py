from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from vinu_live.book.quantize import floor_qty, quantize_qty
from vinu_live.signal_translator import OrderInstruction

LOG = logging.getLogger(__name__)


@dataclass
class ExecutionSlice:
    symbol: str
    side: str
    qty: float
    slice_number: int
    total_slices: int


@dataclass
class ExecutionPlan:
    slices: list[ExecutionSlice] = field(default_factory=list)

    @property
    def total_orders(self) -> int:
        return len(self.slices)


def plan_twap(
    instructions: list[OrderInstruction],
    n_slices: int = 6,
) -> ExecutionPlan:
    """Plan TWAP execution — split each order into n_slices equal slices.

    Each slice is submitted sequentially at regular intervals within the
    execution window, aiming for a time-weighted average price.
    """
    plan = ExecutionPlan()
    for instr in instructions:
        total = quantize_qty(instr.qty)
        if n_slices <= 1 or total <= 0:
            plan.slices.append(ExecutionSlice(
                symbol=instr.symbol, side=instr.side, qty=float(total),
                slice_number=1, total_slices=max(n_slices, 1),
            ))
            continue
        per_slice = total / n_slices
        allocated = Decimal("0")
        for i in range(n_slices):
            is_last = i == n_slices - 1
            slice_qty = total - allocated if is_last else floor_qty(per_slice)
            allocated += slice_qty
            plan.slices.append(ExecutionSlice(
                symbol=instr.symbol,
                side=instr.side,
                qty=float(slice_qty),
                slice_number=i + 1,
                total_slices=n_slices,
            ))
    return plan


def compute_volume_profile(bars: list[dict[str, Any]], n_slices: int) -> list[float]:
    """Bucket a multi-day intraday bar series into n_slices volume-weight
    fractions, so a VWAP plan can put more size where volume historically
    trades instead of splitting evenly like TWAP.

    Bars are grouped by day, then bucketed by each day's *relative* position
    within its own session (bar i of n that day -> bucket floor(i*n_slices/n))
    rather than wall-clock time — this avoids needing timezone-aware
    market-hours math while still reflecting the real intraday volume curve,
    since the upstream provider only returns regular-session bars. Falls back
    to equal weights if there's no usable data, never raises.
    """
    if not bars or n_slices <= 0:
        return [1.0 / max(n_slices, 1)] * max(n_slices, 1)

    by_date: dict[str, list[dict[str, Any]]] = {}
    for b in bars:
        ts = b.get("bar_ts", 0)
        date_key = time.strftime("%Y-%m-%d", time.gmtime(ts))
        by_date.setdefault(date_key, []).append(b)

    bucket_totals = [0.0] * n_slices
    for day_bars in by_date.values():
        day_bars = sorted(day_bars, key=lambda b: b.get("bar_ts", 0))
        n = len(day_bars)
        if n == 0:
            continue
        for i, bar in enumerate(day_bars):
            bucket_idx = min(int(i * n_slices / n), n_slices - 1)
            bucket_totals[bucket_idx] += float(bar.get("volume", 0.0) or 0.0)

    total = sum(bucket_totals)
    if total <= 0:
        return [1.0 / n_slices] * n_slices
    return [t / total for t in bucket_totals]


def plan_vwap(
    instructions: list[OrderInstruction],
    volume_weights: dict[str, list[float]] | None = None,
    n_slices: int = 6,
) -> ExecutionPlan:
    """Plan VWAP execution — split each order across n_slices weighted by a
    historical intraday volume profile (see compute_volume_profile) instead
    of TWAP's equal split, so slice size tracks when the name actually trades.

    volume_weights: {symbol: [w_1..w_n]} fractions (need not be pre-normalized).
    Falls back to equal weighting for any symbol missing from volume_weights,
    with the wrong length, or summing to <= 0 — never drops an order for
    missing volume data. The remainder after rounding is folded into the last
    slice so slice quantities always sum exactly to the order quantity.
    """
    plan = ExecutionPlan()
    volume_weights = volume_weights or {}
    for instr in instructions:
        total = quantize_qty(instr.qty)
        if total <= 0:
            continue
        weights = volume_weights.get(instr.symbol)
        if not weights or len(weights) != n_slices or sum(weights) <= 0:
            weights = [1.0 / n_slices] * n_slices
        else:
            wsum = sum(weights)
            weights = [w / wsum for w in weights]

        allocated = Decimal("0")
        for i, w in enumerate(weights):
            is_last = i == n_slices - 1
            if is_last:
                slice_qty = total - allocated
            else:
                slice_qty = floor_qty(total * Decimal(str(w)))
            allocated += slice_qty
            plan.slices.append(ExecutionSlice(
                symbol=instr.symbol,
                side=instr.side,
                qty=float(slice_qty),
                slice_number=i + 1,
                total_slices=n_slices,
            ))
    return plan


def schedule_slice_delays(n_slices: int, total_window_minutes: int = 60) -> list[int]:
    """Return delay in seconds between each slice submission for TWAP."""
    if n_slices <= 1:
        return []
    delay_sec = (total_window_minutes * 60) // n_slices
    return [delay_sec] * (n_slices - 1)
