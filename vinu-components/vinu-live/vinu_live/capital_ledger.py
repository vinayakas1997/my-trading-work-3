"""Capital ledger: how much of the real-money base is committed, how much is free, and how the closed trades did.

The book owns the committed money (open positions at cost), so the ledger is built here and read by the allocator
(portfolio-api), the order guard (agent-api) and the agent. Everything is for ONE money mode: the book filters by
`account_mode`, and the snapshot says which mode it is, so a paper snapshot can never be read as a real one.

With no capital base configured (`VINU_REAL_CAPITAL` empty) there is no cap: the snapshot says `capped: false`.
"""
from __future__ import annotations

from typing import Any

from vinu_infra.account_mode import current_account_mode, real_capital, reserve_fraction
from vinu_infra.capital import CapitalState
from vinu_live.book.positions import BookBackend, list_closed_positions, list_open_positions


def committed_at_cost(book: BookBackend) -> float:
    """Money held by open long positions, at cost (quantity times average entry)."""
    return sum(p.qty * p.avg_entry for p in list_open_positions(book) if p.side == "long")


def pending_buy_cost(log: Any) -> float:
    """Money promised to buy orders that have not finished filling yet, at the limit (or reference) price, less the part the
    book already holds. Without this a slow order would let the next cycle spend the same dollars twice."""
    if log is None:
        return 0.0
    total = 0.0
    for row in log.unresolved_orders(limit=500):
        if row.get("side") != "buy":
            continue
        price = row.get("limit_price") or row.get("reference_price") or 0.0
        left = max(0.0, float(row.get("qty") or 0.0) - float(row.get("book_applied_qty") or 0.0))
        total += left * float(price)
    return total


def trade_results(book: BookBackend) -> dict[str, Any]:
    """Closed trades of this mode: counts and the average win and loss as a fraction of the position at cost, which are
    the numbers the allocator's win/loss maths needs. Percent figures carry from a paper account to a small real one;
    dollar figures do not."""
    wins: list[float] = []
    losses: list[float] = []
    realized = 0.0
    for row in list_closed_positions(book):
        cost = float(row["qty"]) * float(row["avg_entry"])
        pnl = float(row["realized_pnl"])
        realized += pnl
        if cost <= 0 or abs(pnl) < 1e-12:   # a flat close (including a book cut with no known exit price) is not a result
            continue
        (wins if pnl > 0 else losses).append(abs(pnl) / cost)
    n = len(wins) + len(losses)
    return {
        "account_mode": current_account_mode(),
        "n_closed": n, "n_wins": len(wins), "n_losses": len(losses),
        "win_rate": (len(wins) / n) if n else None,
        "avg_win": (sum(wins) / len(wins)) if wins else None,
        "avg_loss": (sum(losses) / len(losses)) if losses else None,
        "realized_pnl": round(realized, 4),
    }


def capital_snapshot(book: BookBackend, execution_log: Any = None) -> dict[str, Any]:
    mode = current_account_mode()
    base = real_capital()
    positions = [
        {"symbol": p.symbol, "qty": p.qty, "avg_entry": p.avg_entry, "cost": round(p.qty * p.avg_entry, 4),
         "artifact_id": p.artifact_id}
        for p in list_open_positions(book) if p.side == "long"
    ]
    held = committed_at_cost(book)
    pending = pending_buy_cost(execution_log)
    committed = held + pending
    out: dict[str, Any] = {"account_mode": mode, "capped": base is not None, "committed": round(committed, 4),
                           "held_at_cost": round(held, 4), "pending_buys": round(pending, 4),
                           "open_positions": positions, "results": trade_results(book)}
    if base is not None:
        out.update(CapitalState(mode, base, committed, reserve_fraction()).as_dict())
        out["over_committed"] = committed > base
    return out
