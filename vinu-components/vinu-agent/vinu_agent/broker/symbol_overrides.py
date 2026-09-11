"""Persisted, queryable, independently-resettable per-symbol operator
overrides (Stage C, C4 -- and the storage half of C7).

An operator can mark a single symbol ``untradeable`` (reject every order),
``reduce_only`` (allow risk-reducing orders only), or ``ignored`` (drop it
silently -- off the board), each with a free-text reason and who set it.
``OrderGuard`` consults this before any mandate check, so an override
beats a mandate that would otherwise permit the trade. Distinct from the
kill switch (all-or-nothing, safety-critical) and from ``blocked_tickers``
in the mandate (a static, reviewed policy edit, not a runtime incident
response).

SQLite-backed and shared -- same reasoning as ``daily_limits.py``:
``OrderGuard`` is constructed fresh per order, so an in-process dict would
reset every call. Transitions are validated against
``guard_codes.ALLOWED_OVERRIDE_TRANSITIONS`` so a stale client can't push
a symbol into an unexpected state.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from vinu_infra.sqlite import SQLiteBackend

from .guard_codes import OverrideState, transition_allowed

SCHEMA = """
CREATE TABLE IF NOT EXISTS symbol_overrides (
    symbol   TEXT PRIMARY KEY,
    state    TEXT NOT NULL,
    reason   TEXT NOT NULL DEFAULT '',
    set_by   TEXT NOT NULL DEFAULT '',
    set_at   REAL NOT NULL
);
"""

DEFAULT_OVERRIDE_DB_PATH = Path(
    os.environ.get(
        "VINU_AGENT_SYMBOL_OVERRIDE_DB",
        os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu")) + "/symbol_overrides.db",
    )
)


@dataclass(frozen=True)
class OverrideRecord:
    symbol: str
    state: OverrideState
    reason: str
    set_by: str
    set_at: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "state": self.state.value,
            "reason": self.reason,
            "set_by": self.set_by,
            "set_at": self.set_at,
        }


class InvalidOverrideTransition(ValueError):
    pass


class SymbolOverrideStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def get(self, symbol: str) -> OverrideRecord | None:
        row = self._get_conn().execute(
            "SELECT symbol, state, reason, set_by, set_at FROM symbol_overrides WHERE symbol = ?",
            (symbol.upper(),),
        ).fetchone()
        if row is None:
            return None
        try:
            state = OverrideState(row[1])
        except ValueError:
            return None
        return OverrideRecord(row[0], state, row[2] or "", row[3] or "", float(row[4]))

    def all(self) -> list[OverrideRecord]:
        rows = self._get_conn().execute(
            "SELECT symbol, state, reason, set_by, set_at FROM symbol_overrides ORDER BY symbol"
        ).fetchall()
        out: list[OverrideRecord] = []
        for r in rows:
            try:
                out.append(OverrideRecord(r[0], OverrideState(r[1]), r[2] or "", r[3] or "", float(r[4])))
            except ValueError:
                continue
        return out

    def set(self, symbol: str, state: OverrideState, *, reason: str = "", set_by: str = "") -> OverrideRecord:
        symbol = symbol.upper()
        current = self.get(symbol)
        current_state = current.state if current else None
        if not transition_allowed(current_state, state):
            raise InvalidOverrideTransition(
                f"{symbol}: {current_state.value if current_state else 'none'} -> {state.value} is not a permitted transition"
            )
        rec = OverrideRecord(symbol, state, reason, set_by, time.time())
        self.upsert("symbol_overrides", {
            "symbol": rec.symbol, "state": rec.state.value, "reason": rec.reason,
            "set_by": rec.set_by, "set_at": rec.set_at,
        }, conflict_columns=["symbol"])
        self._get_conn().commit()
        return rec

    def clear(self, symbol: str) -> bool:
        """Independently resettable -- one symbol at a time, always allowed."""
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM symbol_overrides WHERE symbol = ?", (symbol.upper(),))
        conn.commit()
        return cur.rowcount > 0


_store: SymbolOverrideStore | None = None


def get_override_store() -> SymbolOverrideStore:
    global _store
    if _store is None:
        _store = SymbolOverrideStore(str(DEFAULT_OVERRIDE_DB_PATH))
    return _store


def reset_override_store(store: SymbolOverrideStore | None = None) -> None:
    """Test hook."""
    global _store
    _store = store
