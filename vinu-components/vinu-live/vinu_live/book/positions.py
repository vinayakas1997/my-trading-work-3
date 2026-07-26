from __future__ import annotations

import hashlib
import logging
from typing import Any

from vinu_lib.sqlite import SQLiteBackend
from vinu_live.book.schema import (
    Position,
    OPEN_POSITIONS_TABLE,
    CLOSED_POSITIONS_TABLE,
    FILLS_TABLE,
    now_iso,
)

LOG = logging.getLogger(__name__)


class BookBackend(SQLiteBackend):
    SCHEMA = f"""
        CREATE TABLE IF NOT EXISTS {OPEN_POSITIONS_TABLE} (
            position_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            avg_entry REAL NOT NULL,
            realized_pnl REAL DEFAULT 0,
            stop_loss REAL,
            take_profit REAL,
            opened_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS {CLOSED_POSITIONS_TABLE} (
            position_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            avg_entry REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            opened_at TEXT NOT NULL,
            closed_at TEXT NOT NULL,
            close_price REAL
        );
        CREATE TABLE IF NOT EXISTS {FILLS_TABLE} (
            fill_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            filled_at TEXT NOT NULL,
            position_id TEXT,
            commission REAL DEFAULT 0
        );
    """
    SCHEMA_VERSION = 2
    # Phase 7: link positions back to the trade-plan artifact that authored them, and track
    # which closed positions the feedback loop has already fed back upstream.
    MIGRATIONS = [
        (f"ALTER TABLE {OPEN_POSITIONS_TABLE} ADD COLUMN artifact_id TEXT DEFAULT ''",
         "add artifact_id to open_positions"),
        (f"ALTER TABLE {CLOSED_POSITIONS_TABLE} ADD COLUMN artifact_id TEXT DEFAULT ''",
         "add artifact_id to closed_positions"),
        (f"ALTER TABLE {CLOSED_POSITIONS_TABLE} ADD COLUMN feedback_processed_at TEXT",
         "add feedback_processed_at to closed_positions"),
    ]


def _position_id(symbol: str, opened_at: str) -> str:
    raw = f"{symbol}:{opened_at}"
    return f"pos_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _fill_id(symbol: str, filled_at: str, qty: float, price: float) -> str:
    raw = f"{symbol}:{filled_at}:{qty}:{price}"
    return f"fill_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def init_book(db_path: str = "data/book.db") -> BookBackend:
    return BookBackend(db_path)


def _conn(backend: BookBackend):
    return backend._get_conn()


def open_position(
    backend: BookBackend,
    symbol: str,
    side: str,
    qty: float,
    price: float,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    commission: float = 0.0,
    artifact_id: str = "",
) -> Position | None:
    try:
        side_lit = _validate_side(side)
    except ValueError as e:
        LOG.warning("Invalid side: %s", e)
        return None

    opened = now_iso()
    pid = _position_id(symbol, opened)
    conn = _conn(backend)
    conn.execute(
        f"INSERT INTO {OPEN_POSITIONS_TABLE} "
        f"(position_id, symbol, side, qty, avg_entry, realized_pnl, stop_loss, take_profit, opened_at, updated_at, artifact_id) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [pid, symbol.upper(), side_lit, qty, price, 0.0, stop_loss, take_profit, opened, opened, artifact_id],
    )
    fid = _fill_id(symbol, opened, qty, price)
    conn.execute(
        f"INSERT INTO {FILLS_TABLE} (fill_id, symbol, side, qty, price, filled_at, position_id, commission) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [fid, symbol.upper(), side, qty, price, opened, pid, commission],
    )
    conn.commit()

    LOG.info("Opened %s %s %s @ %.2f", side, qty, symbol.upper(), price)
    return get_position(backend, pid)


def _validate_side(side: str) -> str:
    s = side.lower()
    if s in ("long", "buy"):
        return "long"
    elif s in ("short", "sell"):
        return "short"
    raise ValueError(f"Invalid side: {side}")


def add_to_position(
    backend: BookBackend,
    position_id: str,
    add_qty: float,
    price: float,
    commission: float = 0.0,
) -> Position | None:
    if add_qty <= 0:
        return None
    pos = get_position(backend, position_id)
    if pos is None:
        return None

    total_qty = pos.qty + add_qty
    total_cost = pos.qty * pos.avg_entry + add_qty * price
    new_avg = total_cost / total_qty if total_qty > 0 else price

    conn = _conn(backend)
    conn.execute(
        f"UPDATE {OPEN_POSITIONS_TABLE} SET qty = ?, avg_entry = ?, updated_at = ? WHERE position_id = ?",
        [total_qty, new_avg, now_iso(), position_id],
    )
    filled_at = now_iso()
    fid = _fill_id(pos.symbol, filled_at, add_qty, price)
    conn.execute(
        f"INSERT INTO {FILLS_TABLE} (fill_id, symbol, side, qty, price, filled_at, position_id, commission) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [fid, pos.symbol, "buy" if pos.side == "long" else "sell", add_qty, price, filled_at, position_id, commission],
    )
    conn.commit()
    return get_position(backend, position_id)


def reduce_position(
    backend: BookBackend,
    position_id: str,
    reduce_qty: float,
    price: float,
    commission: float = 0.0,
) -> Position | None:
    if reduce_qty <= 0:
        return None
    pos = get_position(backend, position_id)
    if pos is None:
        return None

    reduce_qty = min(reduce_qty, pos.qty)
    if reduce_qty <= 0:
        return None

    if pos.side == "long":
        realized = (price - pos.avg_entry) * reduce_qty - commission
    else:
        realized = (pos.avg_entry - price) * reduce_qty - commission

    remaining = pos.qty - reduce_qty
    new_realized = (pos.realized_pnl or 0.0) + realized

    conn = _conn(backend)
    if remaining <= 0:
        _close_position(conn, pos, price, new_realized)
        conn.commit()
        return None

    conn.execute(
        f"UPDATE {OPEN_POSITIONS_TABLE} SET qty = ?, realized_pnl = ?, updated_at = ? WHERE position_id = ?",
        [remaining, new_realized, now_iso(), position_id],
    )
    filled_at = now_iso()
    fid = _fill_id(pos.symbol, filled_at, reduce_qty, price)
    conn.execute(
        f"INSERT INTO {FILLS_TABLE} (fill_id, symbol, side, qty, price, filled_at, position_id, commission) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [fid, pos.symbol, "sell" if pos.side == "long" else "buy", reduce_qty, price, filled_at, position_id, commission],
    )
    conn.commit()
    return get_position(backend, position_id)


def close_position(
    backend: BookBackend,
    position_id: str,
    close_price: float,
    commission: float = 0.0,
) -> Position | None:
    pos = get_position(backend, position_id)
    if pos is None:
        return None

    if pos.side == "long":
        realized = (close_price - pos.avg_entry) * pos.qty - commission
    else:
        realized = (pos.avg_entry - close_price) * pos.qty - commission

    total_realized = (pos.realized_pnl or 0.0) + realized
    conn = _conn(backend)
    _close_position(conn, pos, close_price, total_realized)
    conn.commit()
    return pos


def _close_position(conn, pos: Position, close_price: float, total_realized: float) -> None:
    closed_at = now_iso()
    conn.execute(
        f"INSERT INTO {CLOSED_POSITIONS_TABLE} "
        f"(position_id, symbol, side, qty, avg_entry, realized_pnl, stop_loss, take_profit, opened_at, closed_at, close_price, artifact_id) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [pos.position_id, pos.symbol, pos.side, pos.qty, pos.avg_entry,
         total_realized, pos.stop_loss, pos.take_profit, pos.opened_at, closed_at, close_price, pos.artifact_id],
    )
    conn.execute(
        f"DELETE FROM {OPEN_POSITIONS_TABLE} WHERE position_id = ?",
        [pos.position_id],
    )
    LOG.info("Closed %s position %s — realized PnL: %.2f", pos.symbol, pos.position_id, total_realized)


def get_position(
    backend: BookBackend,
    position_id: str,
) -> Position | None:
    conn = _conn(backend)
    row = conn.execute(
        f"SELECT * FROM {OPEN_POSITIONS_TABLE} WHERE position_id = ?",
        [position_id],
    ).fetchone()
    if row is None:
        return None
    return _row_to_position(dict(row))


def list_open_positions(
    backend: BookBackend,
    symbol: str | None = None,
) -> list[Position]:
    conn = _conn(backend)
    if symbol:
        rows = conn.execute(
            f"SELECT * FROM {OPEN_POSITIONS_TABLE} WHERE symbol = ?",
            [symbol.upper()],
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM {OPEN_POSITIONS_TABLE}").fetchall()
    return [_row_to_position(dict(r)) for r in rows]


def update_stop_loss(
    backend: BookBackend,
    position_id: str,
    stop_loss: float,
) -> Position | None:
    """Tighten (or set) a position's stop -- bookkeeping only, no broker order.

    Used by Phase 6's `tighten_stop` contingency action, which protects a position via a
    resting stop rather than an immediate market order.
    """
    pos = get_position(backend, position_id)
    if pos is None:
        return None
    conn = _conn(backend)
    conn.execute(
        f"UPDATE {OPEN_POSITIONS_TABLE} SET stop_loss = ?, updated_at = ? WHERE position_id = ?",
        [stop_loss, now_iso(), position_id],
    )
    conn.commit()
    return get_position(backend, position_id)


def daily_realized_pnl(backend: BookBackend) -> float:
    """Sum of realized PnL from positions fully closed today (UTC).

    `check_limits()`'s daily-loss check needs this and no prior query provided it. Note: the
    schema records cumulative `realized_pnl` on a position, not a per-fill realized amount, so
    a partial reduce on a position that stays open (and was opened on an earlier day) can't be
    attributed to "today" specifically -- this figure only counts positions closed outright
    today, which is exact for that case rather than an approximation of the other.
    """
    conn = _conn(backend)
    today = now_iso()[:10]
    closed_total = conn.execute(
        f"SELECT COALESCE(SUM(realized_pnl), 0) FROM {CLOSED_POSITIONS_TABLE} "
        f"WHERE closed_at LIKE ?",
        [f"{today}%"],
    ).fetchone()[0]
    return float(closed_total)


def list_closed_positions(
    backend: BookBackend,
    symbol: str | None = None,
    unprocessed_only: bool = False,
) -> list[dict[str, Any]]:
    """Closed positions as plain dicts (including `close_price`/`artifact_id`, which the
    open-position `Position` dataclass doesn't carry) -- Phase 7's feedback loop reads this.
    """
    conn = _conn(backend)
    conditions: list[str] = []
    params: list[Any] = []
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol.upper())
    if unprocessed_only:
        conditions.append("feedback_processed_at IS NULL")
        conditions.append("artifact_id != ''")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM {CLOSED_POSITIONS_TABLE} {where} ORDER BY closed_at ASC", params,
    ).fetchall()
    return [dict(r) for r in rows]


def mark_feedback_processed(backend: BookBackend, position_id: str) -> None:
    conn = _conn(backend)
    conn.execute(
        f"UPDATE {CLOSED_POSITIONS_TABLE} SET feedback_processed_at = ? WHERE position_id = ?",
        [now_iso(), position_id],
    )
    conn.commit()


def _row_to_position(row: dict[str, Any]) -> Position:
    return Position(
        position_id=row["position_id"],
        symbol=row["symbol"],
        side=row["side"],
        qty=row["qty"],
        avg_entry=row["avg_entry"],
        realized_pnl=row.get("realized_pnl", 0.0),
        stop_loss=row.get("stop_loss"),
        take_profit=row.get("take_profit"),
        opened_at=row["opened_at"],
        updated_at=row["updated_at"],
        artifact_id=row.get("artifact_id", "") or "",
    )
