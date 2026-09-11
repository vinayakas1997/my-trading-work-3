"""Stage C (C7) — persisted, queryable, independently-resettable
per-instrument trade-limit *value* storage, ported from pysystemtrade's
override-precedence model (`12-pysystemtrade.md`). C4's
`symbol_overrides.py` already delivered the storage half in the sense that
matters most (SQLite-backed, per-symbol, independently-resettable) — but
its `OverrideState` is a coarse trade-permission switch (untradeable /
reduce_only / ignored), not a *value*. This module is the other half: a
symbol whose limits should be tighter than the mandate's global defaults
without being untradeable at all (a volatile small-cap that should get a
smaller `max_order_value` than everything else, say), plus a queryable
history of every change so "why is AAPL capped at $500?" has an answer.

Same `SQLiteBackend` convention as `symbol_overrides.py`/`audit_ledger.py`.
A `None` field means "no override — inherit the mandate's global value,"
so setting a limit is opt-in per symbol, per field; `clear()` removes a
symbol's overrides entirely (back to 100% mandate-derived), independently
of every other symbol, same as `SymbolOverrideStore.clear()`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS symbol_limits (
    symbol                        TEXT PRIMARY KEY,
    max_order_value               REAL,
    max_position_pct              REAL,
    max_capital_utilization_pct   REAL,
    reason                        TEXT NOT NULL DEFAULT '',
    set_by                        TEXT NOT NULL DEFAULT '',
    set_at                        REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS symbol_limit_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol     TEXT NOT NULL,
    field      TEXT NOT NULL,
    old_value  REAL,
    new_value  REAL,
    reason     TEXT NOT NULL DEFAULT '',
    set_by     TEXT NOT NULL DEFAULT '',
    changed_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_symbol_limit_history_symbol ON symbol_limit_history(symbol, changed_at);
"""

DEFAULT_LIMIT_DB_PATH = Path(
    os.environ.get(
        "VINU_AGENT_SYMBOL_LIMIT_DB",
        os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu")) + "/symbol_limits.db",
    )
)

_LIMIT_FIELDS = ("max_order_value", "max_position_pct", "max_capital_utilization_pct")


@dataclass(frozen=True)
class LimitRecord:
    symbol: str
    max_order_value: float | None
    max_position_pct: float | None
    max_capital_utilization_pct: float | None
    reason: str
    set_by: str
    set_at: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "max_order_value": self.max_order_value,
            "max_position_pct": self.max_position_pct,
            "max_capital_utilization_pct": self.max_capital_utilization_pct,
            "reason": self.reason,
            "set_by": self.set_by,
            "set_at": self.set_at,
        }


@dataclass(frozen=True)
class LimitHistoryEntry:
    symbol: str
    field: str
    old_value: float | None
    new_value: float | None
    reason: str
    set_by: str
    changed_at: float


class SymbolLimitStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def get(self, symbol: str) -> LimitRecord | None:
        row = self._get_conn().execute(
            "SELECT symbol, max_order_value, max_position_pct, max_capital_utilization_pct, "
            "reason, set_by, set_at FROM symbol_limits WHERE symbol = ?",
            (symbol.upper(),),
        ).fetchone()
        if row is None:
            return None
        return LimitRecord(row[0], row[1], row[2], row[3], row[4] or "", row[5] or "", float(row[6]))

    def all(self) -> list[LimitRecord]:
        rows = self._get_conn().execute(
            "SELECT symbol, max_order_value, max_position_pct, max_capital_utilization_pct, "
            "reason, set_by, set_at FROM symbol_limits ORDER BY symbol"
        ).fetchall()
        return [
            LimitRecord(r[0], r[1], r[2], r[3], r[4] or "", r[5] or "", float(r[6]))
            for r in rows
        ]

    def set(
        self,
        symbol: str,
        *,
        max_order_value: float | None = None,
        max_position_pct: float | None = None,
        max_capital_utilization_pct: float | None = None,
        reason: str = "",
        set_by: str = "",
    ) -> LimitRecord:
        """Merges into the symbol's current record -- an omitted (`None`)
        keyword argument leaves that field's existing override untouched
        (it does NOT clear it back to "inherit"; use `clear_field()` for
        that). Every field that actually *changes* value gets one
        `symbol_limit_history` row, so "AAPL's max_order_value went from
        $1000 to $500 on 2026-09-11" is answerable without reconstructing
        it from the mandate/config diff."""
        symbol = symbol.upper()
        now = time.time()
        current = self.get(symbol)
        requested = {
            "max_order_value": max_order_value,
            "max_position_pct": max_position_pct,
            "max_capital_utilization_pct": max_capital_utilization_pct,
        }
        new_values = {
            field: (requested[field] if requested[field] is not None else (getattr(current, field) if current else None))
            for field in _LIMIT_FIELDS
        }

        history_rows = []
        for field in _LIMIT_FIELDS:
            if requested[field] is None:
                continue  # caller didn't touch this field -- no change to log
            old = getattr(current, field) if current else None
            new = new_values[field]
            if old != new:
                history_rows.append((symbol, field, old, new, reason, set_by, now))

        rec = LimitRecord(symbol, new_values["max_order_value"], new_values["max_position_pct"],
                           new_values["max_capital_utilization_pct"], reason, set_by, now)
        conn = self._get_conn()
        self.upsert("symbol_limits", {
            "symbol": rec.symbol,
            "max_order_value": rec.max_order_value,
            "max_position_pct": rec.max_position_pct,
            "max_capital_utilization_pct": rec.max_capital_utilization_pct,
            "reason": rec.reason,
            "set_by": rec.set_by,
            "set_at": rec.set_at,
        }, conflict_columns=["symbol"])
        if history_rows:
            conn.executemany(
                "INSERT INTO symbol_limit_history (symbol, field, old_value, new_value, reason, set_by, changed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                history_rows,
            )
        conn.commit()
        return rec

    def clear_field(self, symbol: str, field: str, *, reason: str = "", set_by: str = "") -> LimitRecord | None:
        """Reset a single field back to "inherit the mandate default"
        without touching the symbol's other overrides -- unlike `set()`,
        where omitting a field leaves it alone, this explicitly nulls it
        out and logs the change to history."""
        if field not in _LIMIT_FIELDS:
            raise ValueError(f"unknown limit field {field!r}, expected one of {_LIMIT_FIELDS}")
        symbol = symbol.upper()
        current = self.get(symbol)
        if current is None or getattr(current, field) is None:
            return current
        now = time.time()
        old = getattr(current, field)
        values = {f: getattr(current, f) for f in _LIMIT_FIELDS}
        values[field] = None
        rec = LimitRecord(symbol, values["max_order_value"], values["max_position_pct"],
                           values["max_capital_utilization_pct"], reason or current.reason, set_by or current.set_by, now)
        conn = self._get_conn()
        self.upsert("symbol_limits", {
            "symbol": rec.symbol,
            "max_order_value": rec.max_order_value,
            "max_position_pct": rec.max_position_pct,
            "max_capital_utilization_pct": rec.max_capital_utilization_pct,
            "reason": rec.reason,
            "set_by": rec.set_by,
            "set_at": rec.set_at,
        }, conflict_columns=["symbol"])
        conn.execute(
            "INSERT INTO symbol_limit_history (symbol, field, old_value, new_value, reason, set_by, changed_at) "
            "VALUES (?, ?, ?, NULL, ?, ?, ?)",
            (symbol, field, old, reason, set_by, now),
        )
        conn.commit()
        return rec

    def clear(self, symbol: str) -> bool:
        """Independently resettable -- one symbol at a time, back to
        100% mandate-derived limits, always allowed (no precedence
        transitions to validate here — unlike C4's override states, a
        limit-value override has no "current state" that could make
        clearing it invalid)."""
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM symbol_limits WHERE symbol = ?", (symbol.upper(),))
        conn.commit()
        return cur.rowcount > 0

    def history(self, symbol: str | None = None, *, limit: int = 100) -> list[LimitHistoryEntry]:
        conn = self._get_conn()
        if symbol is not None:
            rows = conn.execute(
                "SELECT symbol, field, old_value, new_value, reason, set_by, changed_at "
                "FROM symbol_limit_history WHERE symbol = ? ORDER BY changed_at DESC LIMIT ?",
                (symbol.upper(), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT symbol, field, old_value, new_value, reason, set_by, changed_at "
                "FROM symbol_limit_history ORDER BY changed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [LimitHistoryEntry(r[0], r[1], r[2], r[3], r[4] or "", r[5] or "", float(r[6])) for r in rows]


_store: SymbolLimitStore | None = None


def get_limit_store() -> SymbolLimitStore:
    global _store
    if _store is None:
        _store = SymbolLimitStore(str(DEFAULT_LIMIT_DB_PATH))
    return _store


def reset_limit_store(store: SymbolLimitStore | None = None) -> None:
    """Test hook."""
    global _store
    _store = store
