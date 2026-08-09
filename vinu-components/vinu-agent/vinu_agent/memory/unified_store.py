from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    source_id   TEXT DEFAULT '',
    symbol      TEXT NOT NULL DEFAULT '',
    memory_type TEXT NOT NULL DEFAULT 'note',
    title       TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    summary     TEXT NOT NULL DEFAULT '',
    metadata    TEXT NOT NULL DEFAULT '{}',
    score       REAL DEFAULT 0.0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_watermarks (
    source       TEXT PRIMARY KEY,
    last_sync_at TEXT NOT NULL DEFAULT '',
    last_id      TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_mem_source ON memory_entries(source);
CREATE INDEX IF NOT EXISTS idx_mem_symbol ON memory_entries(symbol);
CREATE INDEX IF NOT EXISTS idx_mem_type ON memory_entries(memory_type);
CREATE INDEX IF NOT EXISTS idx_mem_source_symbol ON memory_entries(source, symbol);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    title, content, summary, symbol, memory_type,
    tokenize='porter unicode61',
    content='memory_entries',
    content_rowid='rowid'
);
"""

SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[str, str]] = []


@dataclass
class MemoryEntry:
    id: str
    source: str
    source_id: str = ""
    symbol: str = ""
    memory_type: str = "note"
    title: str = ""
    content: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["metadata"] = json.dumps(self.metadata) if isinstance(self.metadata, dict) else self.metadata
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> MemoryEntry:
        meta = row.get("metadata", "{}")
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        return cls(
            id=row["id"],
            source=row["source"],
            source_id=row.get("source_id", ""),
            symbol=row.get("symbol", ""),
            memory_type=row.get("memory_type", "note"),
            title=row.get("title", ""),
            content=row.get("content", ""),
            summary=row.get("summary", ""),
            metadata=meta,
            score=row.get("score", 0.0) or 0.0,
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class UnifiedMemoryStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def __init__(self, db_path: str | Path) -> None:
        super().__init__(db_path)
        self._init_fts()

    def _init_fts(self) -> None:
        conn = self._get_conn()
        conn.executescript(FTS_SCHEMA)
        conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_entry(self, entry: MemoryEntry) -> str:
        if not entry.id:
            entry.id = _new_id()
        now = _now()
        if not entry.created_at:
            entry.created_at = now
        entry.updated_at = now

        data = entry.to_dict()
        self.upsert("memory_entries", data, conflict_columns=["id"])
        self._sync_fts_row(entry)
        return entry.id

    def get_entry(self, entry_id: str) -> MemoryEntry | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM memory_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        return MemoryEntry.from_row(dict(row))

    def delete_entry(self, entry_id: str) -> bool:
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT 1 FROM memory_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if existing is None:
            return False
        conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
        conn.execute(
            "DELETE FROM memory_fts WHERE rowid NOT IN (SELECT rowid FROM memory_entries)"
        )
        conn.commit()
        return True

    def delete_entries_by_source(self, source: str) -> int:
        conn = self._get_conn()
        conn.execute("DELETE FROM memory_entries WHERE source = ?", (source,))
        conn.execute("DELETE FROM memory_fts WHERE rowid NOT IN (SELECT rowid FROM memory_entries)")
        conn.commit()
        return conn.total_changes

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    SOURCE_WEIGHTS = {
        "research": 3.0,
        "simulator": 2.5,
        "stock_price": 2.0,
        "agent": 2.0,
        "news": 1.0,
    }

    def _compute_composite_score(self, entry: MemoryEntry, fts_rank: float | None = None) -> float:
        source_weight = self.SOURCE_WEIGHTS.get(entry.source, 1.0)

        recency_days = 365.0
        if entry.updated_at:
            try:
                updated = time.mktime(time.strptime(entry.updated_at, "%Y-%m-%dT%H:%M:%SZ"))
                now = time.time()
                age_days = (now - updated) / 86400.0
                recency_factor = max(0.1, 1.0 - age_days / recency_days)
            except (ValueError, OSError):
                recency_factor = 0.5
        else:
            recency_factor = 0.5

        stored_score = max(0.0, entry.score) / 10.0

        if fts_rank is not None:
            fts_score = max(0.0, 1.0 - abs(fts_rank) / 100.0)
        else:
            fts_score = 0.5

        return source_weight * 0.4 + recency_factor * 0.3 + fts_score * 0.2 + stored_score * 0.1

    def scored_search(
        self,
        query: str = "",
        source: str | None = None,
        symbol: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
        dedup: bool = True,
    ) -> list[MemoryEntry]:
        conn = self._get_conn()
        clauses: list[str] = []
        params: list[Any] = []

        has_query = bool(query and query.strip())
        if has_query:
            fts_join = ", memory_fts"
            clauses.append("e.rowid = memory_fts.rowid AND memory_fts MATCH ?")
            params.append(query.strip())
        else:
            fts_join = ""

        if source:
            clauses.append("e.source = ?")
            params.append(source)
        if symbol:
            clauses.append("e.symbol = ?")
            params.append(symbol.upper())
        if memory_type:
            clauses.append("e.memory_type = ?")
            params.append(memory_type)

        where = " AND ".join(clauses) if clauses else "1=1"

        fetch_limit = limit * 3 if dedup else limit
        sql = f"""
            SELECT e.* {', memory_fts.rank AS fts_rank' if has_query else ', NULL AS fts_rank'}
            FROM memory_entries e {fts_join}
            WHERE {where}
            ORDER BY e.updated_at DESC
            LIMIT ?
        """
        params.append(fetch_limit)
        rows = conn.execute(sql, params).fetchall()

        results: list[MemoryEntry] = []
        seen_sources: set[tuple[str, str]] = set()

        for row in rows:
            entry = MemoryEntry.from_row(dict(row))
            fts_rank_val = row["fts_rank"] if has_query else None
            entry.score = self._compute_composite_score(entry, fts_rank=fts_rank_val)

            if dedup:
                dedup_key = (entry.source, entry.source_id)
                if dedup_key in seen_sources:
                    continue
                if entry.source_id:
                    seen_sources.add(dedup_key)

            results.append(entry)

        results.sort(key=lambda e: e.score, reverse=True)
        return results[:limit]

    def search(
        self,
        query: str,
        source: str | None = None,
        symbol: str | None = None,
        memory_type: str | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        return self.scored_search(
            query=query, source=source, symbol=symbol,
            memory_type=memory_type, limit=limit, dedup=True,
        )

    def list_by_symbol(
        self,
        symbol: str,
        source: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        return self.scored_search(
            query="", symbol=symbol, source=source, limit=limit, dedup=True,
        )

    def list_by_symbol(
        self,
        symbol: str,
        source: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        return self.search(
            query="",
            symbol=symbol,
            source=source,
            limit=limit,
        )

    def recent_entries(
        self,
        limit: int = 20,
        source: str | None = None,
    ) -> list[MemoryEntry]:
        conn = self._get_conn()
        if source:
            rows = conn.execute(
                "SELECT * FROM memory_entries WHERE source = ? ORDER BY updated_at DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memory_entries ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [MemoryEntry.from_row(dict(r)) for r in rows]

    def count(self, source: str | None = None) -> int:
        conn = self._get_conn()
        if source:
            row = conn.execute(
                "SELECT COUNT(*) FROM memory_entries WHERE source = ?", (source,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Sync watermarks
    # ------------------------------------------------------------------

    def get_watermark(self, source: str) -> dict[str, str]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sync_watermarks WHERE source = ?", (source,)
        ).fetchone()
        if row is None:
            return {"source": source, "last_sync_at": "", "last_id": ""}
        return dict(row)

    def set_watermark(self, source: str, last_id: str = "") -> None:
        now = _now()
        data = {
            "source": source,
            "last_sync_at": now,
            "last_id": last_id,
        }
        self.upsert("sync_watermarks", data, conflict_columns=["source"])

    # ------------------------------------------------------------------
    # FTS sync helpers
    # ------------------------------------------------------------------

    def _sync_fts_row(self, entry: MemoryEntry) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO memory_fts(rowid, title, content, summary, symbol, memory_type) "
            "VALUES ("
            "  (SELECT rowid FROM memory_entries WHERE id = ?), "
            "  ?, ?, ?, ?, ?"
            ")",
            (
                entry.id,
                entry.title,
                entry.content,
                entry.summary,
                entry.symbol,
                entry.memory_type,
            ),
        )
        conn.commit()

    def _sync_fts_rows_many(self, entries: list[MemoryEntry]) -> None:
        conn = self._get_conn()
        conn.executemany(
            "INSERT OR REPLACE INTO memory_fts(rowid, title, content, summary, symbol, memory_type) "
            "VALUES ("
            "  (SELECT rowid FROM memory_entries WHERE id = ?), "
            "  ?, ?, ?, ?, ?"
            ")",
            [
                (entry.id, entry.title, entry.content, entry.summary, entry.symbol, entry.memory_type)
                for entry in entries
            ],
        )
        conn.commit()

    def rebuild_fts(self) -> None:
        conn = self._get_conn()
        conn.executescript(
            "DELETE FROM memory_fts; "
            "INSERT INTO memory_fts(rowid, title, content, summary, symbol, memory_type) "
            "SELECT rowid, title, content, summary, symbol, memory_type FROM memory_entries;"
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def bulk_add(self, entries: list[MemoryEntry]) -> int:
        # Real fix: this used to call add_entry() per entry, and add_entry()
        # itself commits twice per call (once in upsert(), once in
        # _sync_fts_row()) -- so a "bulk" add of N entries did 2*N
        # fsync-backed commits, one row at a time, defeating the entire
        # point of a bulk path. Now one commit for the entries table, one
        # commit for the FTS sync, regardless of N.
        if not entries:
            return 0
        now = _now()
        for entry in entries:
            if not entry.id:
                entry.id = _new_id()
            if not entry.created_at:
                entry.created_at = now
            entry.updated_at = now

        self.upsert_many(
            "memory_entries", [entry.to_dict() for entry in entries], conflict_columns=["id"]
        )
        self._sync_fts_rows_many(entries)
        return len(entries)

    def clear_and_rebuild(self, source: str | None = None) -> int:
        conn = self._get_conn()
        if source:
            conn.execute("DELETE FROM memory_entries WHERE source = ?", (source,))
        else:
            conn.execute("DELETE FROM memory_entries")
        self.rebuild_fts()
        conn.commit()
        return self.count()
