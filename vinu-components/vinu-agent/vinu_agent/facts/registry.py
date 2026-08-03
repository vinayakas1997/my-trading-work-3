"""Facts & Limitations Registry — machine-readable store for permanent facts
("direction prediction from sentiment/FinBERT doesn't work") and this
project's own documented failure modes ("agent fabricated a JNJ price"), so a
future agent instance can't silently rediscover a disproven approach or
repeat a mistake this project already paid to learn from once.

Same SQLiteBackend subclass pattern as UnifiedMemoryStore
(vinu_agent/memory/unified_store.py) — own .db file, no vector DB needed.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vinu_lib.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id                TEXT PRIMARY KEY,
    statement         TEXT NOT NULL,
    kind              TEXT NOT NULL,
    symbols           TEXT NOT NULL DEFAULT '[]',
    signals           TEXT NOT NULL DEFAULT '[]',
    evidence_ref      TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'active',
    established_date  TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);
CREATE INDEX IF NOT EXISTS idx_facts_kind ON facts(kind);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []

VALID_KINDS = {"proven", "disproven", "known-bug"}
VALID_STATUSES = {"active", "superseded"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class Fact:
    id: str
    statement: str
    kind: str
    symbols: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    evidence_ref: str = ""
    status: str = "active"
    established_date: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["symbols"] = json.dumps(self.symbols)
        d["signals"] = json.dumps(self.signals)
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Fact":
        def _loads(v: Any) -> list[str]:
            if isinstance(v, str):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    return []
            return list(v) if v else []

        return cls(
            id=row["id"],
            statement=row["statement"],
            kind=row["kind"],
            symbols=_loads(row.get("symbols")),
            signals=_loads(row.get("signals")),
            evidence_ref=row.get("evidence_ref", ""),
            status=row.get("status", "active"),
            established_date=row.get("established_date", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )


class FactsRegistry(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def add_fact(self, fact: Fact) -> str:
        if fact.kind not in VALID_KINDS:
            raise ValueError(f"invalid kind: {fact.kind!r} (expected one of {VALID_KINDS})")
        if fact.status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {fact.status!r} (expected one of {VALID_STATUSES})")

        if not fact.id:
            fact.id = _new_id()
        now = _now()
        if not fact.created_at:
            fact.created_at = now
        fact.updated_at = now

        self.upsert("facts", fact.to_dict(), conflict_columns=["id"])

        try:
            from ..broker.kill_switch import AuditLogger

            AuditLogger.log(
                AuditLogger.FACT_REGISTRY_WRITE,
                details={"statement": fact.statement, "kind": fact.kind, "id": fact.id},
                symbol=",".join(fact.symbols),
            )
        except Exception:
            pass

        return fact.id

    def supersede(self, fact_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE facts SET status = 'superseded', updated_at = ? WHERE id = ?",
            (_now(), fact_id),
        )
        conn.commit()

    def count_active(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM facts WHERE status = 'active'").fetchone()
        return row[0] if row else 0

    def active_facts_for(
        self, symbols: list[str] | None = None, signals: list[str] | None = None
    ) -> list[Fact]:
        """Active facts scoped to any of *symbols*/*signals*, plus facts with
        no symbol/signal scoping at all — those apply universally (e.g. the
        direction-prediction finding, which isn't specific to one ticker)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM facts WHERE status = 'active' ORDER BY created_at ASC"
        ).fetchall()

        want_symbols = {s.upper() for s in (symbols or []) if s}
        want_signals = set(signals or [])

        result: list[Fact] = []
        for row in rows:
            f = Fact.from_row(dict(row))
            if not f.symbols and not f.signals:
                result.append(f)
                continue
            if f.symbols and want_symbols & {s.upper() for s in f.symbols}:
                result.append(f)
                continue
            if f.signals and want_signals & set(f.signals):
                result.append(f)
                continue
        return result
