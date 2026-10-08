"""Bring the book back in line with the broker when a position was closed or cut outside the scheduler.

A sell sent straight to the agent endpoint (a manual exit, a stop, a bracket leg) never passes through the scheduler's
fill write-back, so the book kept showing a position the broker no longer held. With a real-money base that phantom position
counts as committed money, and the capital stays locked for good (found in the live drill, 2026-10-08).

Reduce-only by design: where the broker holds LESS than the book says, the book is cut down to the broker's quantity. Where the
broker holds MORE (a hand-placed purchase, a buy not yet written back) the book is left alone, because the book only ever
records what the system itself bought. The exit price is unknown here, so the cut is made at the entry price (realized P&L
zero) and reported, never invented.
"""
from __future__ import annotations

from typing import Any

from vinu_live.book.positions import BookBackend, close_position, list_open_positions, reduce_position

EPS = 1e-9


def sync_book_to_broker(book: BookBackend, broker_qty: dict[str, float]) -> list[dict[str, Any]]:
    adjustments: list[dict[str, Any]] = []
    by_symbol: dict[str, list] = {}
    for p in list_open_positions(book):
        if p.side == "long":
            by_symbol.setdefault(p.symbol.upper(), []).append(p)
    broker = {str(k).upper(): float(v) for k, v in broker_qty.items()}
    for symbol, positions in by_symbol.items():
        excess = sum(p.qty for p in positions) - max(0.0, broker.get(symbol, 0.0))
        for p in positions:
            if excess <= EPS:
                break
            cut = min(p.qty, excess)
            if cut >= p.qty - EPS:
                close_position(book, p.position_id, p.avg_entry)
            else:
                reduce_position(book, p.position_id, cut, p.avg_entry)
            adjustments.append({"symbol": symbol, "position_id": p.position_id, "cut_qty": round(cut, 6),
                                "at": p.avg_entry, "why": "broker holds less than the book"})
            excess -= cut
    return adjustments
