"""Stage B (B17): fired-watch audit retention split, ported from
FinceptTerminal's `scan_watch_events` table (`13-fincept-terminal.md`).
Live rule-gating state (Phase B-2's `CooldownGate`/`FireState`, and Phase
B-4's one-shot deactivation, `monitor.py`) is transient and *current* --
it answers "is this rule armed right now." This module answers a different
question, permanently: "why did this symbol get surfaced, and when" -- a
fire is written here once and never mutated or reset, even if the live
rule's cooldown state, or the rule itself, is later edited or removed.

Same `SQLiteBackend` convention `vinu-agent`'s `symbol_overrides.py` and
`audit_ledger.py` already use elsewhere in Vina.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from vinu_infra.sqlite import SQLiteBackend


@dataclass(frozen=True)
class FiredWatchRecord:
    rule_id: str
    symbol: str
    fired_at: float
    detail: str = ""


class WatchAuditStore(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS fired_watches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        fired_at REAL NOT NULL,
        detail TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_fired_watches_rule ON fired_watches(rule_id, fired_at);
    CREATE INDEX IF NOT EXISTS idx_fired_watches_symbol ON fired_watches(symbol, fired_at);
    """
    SCHEMA_VERSION = 1

    def record_fire(self, rule_id: str, symbol: str, *, detail: str = "", now: float | None = None) -> None:
        now = now if now is not None else time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO fired_watches (rule_id, symbol, fired_at, detail) VALUES (?, ?, ?, ?)",
            (rule_id, symbol, now, detail),
        )
        conn.commit()

    def record_many(self, records: list[FiredWatchRecord]) -> None:
        if not records:
            return
        conn = self._get_conn()
        conn.executemany(
            "INSERT INTO fired_watches (rule_id, symbol, fired_at, detail) VALUES (?, ?, ?, ?)",
            [(r.rule_id, r.symbol, r.fired_at, r.detail) for r in records],
        )
        conn.commit()

    def history(
        self,
        *,
        rule_id: str | None = None,
        symbol: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[FiredWatchRecord]:
        conn = self._get_conn()
        clauses = []
        params: list[object] = []
        if rule_id is not None:
            clauses.append("rule_id = ?")
            params.append(rule_id)
        if symbol is not None:
            clauses.append("symbol = ?")
            params.append(symbol)
        if since is not None:
            clauses.append("fired_at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT rule_id, symbol, fired_at, detail FROM fired_watches {where} "
            f"ORDER BY fired_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [FiredWatchRecord(row["rule_id"], row["symbol"], row["fired_at"], row["detail"]) for row in rows]

    def count(self, *, rule_id: str | None = None) -> int:
        conn = self._get_conn()
        if rule_id is not None:
            return conn.execute("SELECT COUNT(*) FROM fired_watches WHERE rule_id = ?", (rule_id,)).fetchone()[0]
        return conn.execute("SELECT COUNT(*) FROM fired_watches").fetchone()[0]
